import Foundation

@main struct InspectionOutboxTests {
 static var checks = 0
 static func check(_ value: Bool, _ name: String) { checks += 1; if !value { fatalError("FAIL: \(name)") } }
 static func rejects(_ name: String, _ action: () throws -> Void) { do { try action(); fatalError("FAIL accepted: \(name)") } catch { checks += 1 } }
 static func rejectsAsync(_ name: String, _ action: () async throws -> Void) async { do { try await action(); fatalError("FAIL accepted: \(name)") } catch { checks += 1 } }
 static let owner="11111111-1111-4111-8111-111111111111", protocolID="22222222-2222-4222-8222-222222222222"
 static let draftID="33333333-3333-4333-8333-333333333333", roomID="44444444-4444-4444-8444-444444444444", findingID="55555555-5555-4555-8555-555555555555", photoID="66666666-6666-4666-8666-666666666666", operationID="77777777-7777-4777-8777-777777777777"
 static let at="2026-10-21T10:00:00.000Z"
 static func snapshot(title: String="Wohnung Ä / 🔧", extra: String="") throws -> InspectionJSON {
  try InspectionJSON.parse(Data("""
  {"protocol":{"id":"\(protocolID)","organization_id":null,"title":"\(title)","status":"draft","updated_at":"\(at)"\(extra)},"rooms":[],"findings":[]}
  """.utf8))
 }
 static func fresh(_ identifier: String=draftID) throws -> InspectionDraft { try InspectionDraft.create(id:identifier,ownerID:owner,organizationID:nil,snapshot:snapshot(),at:at) }
 static func main() async throws {
  let canonical=try InspectionJSON.parse(Data(#"{"z":"a/b\nÄ🔧","a":true,"n":null,"i":12}"#.utf8)).canonical
  check(canonical == #"{"a":true,"i":12,"n":null,"z":"a/b\nÄ🔧"}"#, "canonical Unicode/slash/control ordering matches JS")
  try rejects("unsafe integer") { _ = try InspectionJSON.parse(Data("9007199254740992".utf8)) }
  var draft=try fresh()
  check(draft.ownerID==owner && draft.state == .draft && draft.revision==0,"new draft has scoped identity")
  check(try InspectionDraft.create(id:draftID,ownerID:owner,organizationID:nil,snapshot:snapshot(extra:",\"property_name\":\"Display only\""),at:at).baseline == draft.baseline,"known joined fields stripped")
  rejects("unknown baseline fields") { _ = try InspectionDraft.create(id:draftID,ownerID:owner,organizationID:nil,snapshot:snapshot(extra:",\"unknown\":true"),at:at) }
  rejects("wrong scope") { _ = try InspectionDraft.create(id:draftID,ownerID:owner,organizationID:roomID,snapshot:snapshot(),at:at) }
  draft=try draft.addingRoom(InspectionRoom(id:roomID,name:" Küche ",condition:"notice",notes:"Ä 🔧"))
  check(draft.rooms.first?.name == "Küche","room names trimmed")
  rejects("duplicate room") { _ = try draft.addingRoom(draft.rooms[0]) }
  rejects("blank room") { _ = try draft.addingRoom(InspectionRoom(id:photoID,name:"  ",condition:"ok",notes:"")) }
  rejects("room condition") { _ = try draft.addingRoom(InspectionRoom(id:photoID,name:"Bad",condition:"bad",notes:"")) }
  rejects("orphan finding") { _ = try draft.addingFinding(InspectionFinding(id:findingID,roomID:photoID,title:"Fuge",description:"Offen",category:"Sonstiges",severity:"normal")) }
  draft=try draft.addingFinding(InspectionFinding(id:findingID,roomID:roomID,title:"Fuge",description:"Offen",category:"Sonstiges",severity:"normal"))
  let bytes=Data([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])
  let photo=try InspectionPhoto(id:photoID,findingID:findingID,name:"Foto.png",mime:"image/png",data:bytes)
  draft=try draft.addingPhoto(photo)
  check(photo.sha256.count==64 && photo.size==bytes.count,"photo binds exact data")
  rejects("unsupported photo") { _ = try InspectionPhoto(id:operationID,findingID:findingID,name:"x.heic",mime:"image/heic",data:bytes) }
  rejects("oversized photo") { _ = try InspectionPhoto(id:operationID,findingID:findingID,name:"x.png",mime:"image/png",data:Data(repeating:0,count:3*1024*1024+1)) }
  // The backend limits the complete canonical payload, not just its baseline.
  func payloadSizedDraft(_ byteCount: Int) throws -> InspectionDraft {
   var value = try fresh().addingRoom(InspectionRoom(id:roomID,name:"Raum",condition:"ok",notes:""))
   var root = value.baseline.object!
   var protocolValue = root["protocol"]!.object!
   protocolValue["general_notes"] = .string("🔧")
   root["protocol"] = .object(protocolValue); value.baseline = .object(root)
   let padding = byteCount - (try value.payload(operationID)).utf8.count
   protocolValue["general_notes"] = .string("🔧" + String(repeating:"x",count:padding))
   root["protocol"] = .object(protocolValue); value.baseline = .object(root)
   try value.validate(); return value
  }
  let boundary = try payloadSizedDraft(1024*1024)
  check(try boundary.sealed(operationID:operationID,at:at).batchPayload!.utf8.count == 1024*1024,"exact backend UTF8 capacity accepted")
  let oversized = try payloadSizedDraft(1024*1024+1)
  let editableBefore = oversized
  do {
   _ = try oversized.sealed(operationID:operationID,at:at)
   fatalError("FAIL accepted: oversized canonical payload sealed")
  } catch InspectionError.capacity { checks += 1 }
  check(oversized == editableBefore && oversized.state == .draft && oversized.operationID == nil,"capacity failure retains editable unchanged draft")
  let queued=try draft.sealed(operationID:operationID,at:at)
  check(queued.batchPayload?.contains("\"operationID\":\"\(operationID)\"")==true,"sealed canonical wire identity")
  check(queued.batchPayload?.contains("Wohnung Ä / 🔧")==true,"wire preserves UTF8")
  rejects("sealed immutable") { _ = try queued.addingRoom(InspectionRoom(id:operationID,name:"Bad",condition:"ok",notes:"")) }
  let result: InspectionJSON = .object(["rooms":.object([roomID:.string("server-room")]),"findings":.object([findingID:.string("server-finding")]),"photos":.object([photoID:.string("server-photo")])])
  let receipt=InspectionReceipt(operationID:operationID,protocolID:protocolID,ownerID:owner,payload:queued.batchPayload!,result:result)
  check(try queued.acknowledged(receipt).state == .acknowledged,"exact receipt accepted")
  rejects("wrong actor receipt") { _ = try queued.acknowledged(InspectionReceipt(operationID:operationID,protocolID:protocolID,ownerID:roomID,payload:queued.batchPayload!,result:result)) }
  rejects("missing mapping") { _ = try queued.acknowledged(InspectionReceipt(operationID:operationID,protocolID:protocolID,ownerID:owner,payload:queued.batchPayload!,result:.object([:]))) }
  let absent=InspectionCancellation(ownerID:owner,protocolID:protocolID,operationID:operationID,payload:queued.batchPayload!,cancelled:false)
  rejects("absence does not unlock") { _ = try queued.rebased(snapshot:snapshot(),evidence:absent,confirmed:true) }
  let cancelled=InspectionCancellation(ownerID:owner,protocolID:protocolID,operationID:operationID,payload:queued.batchPayload!,cancelled:true)
  rejects("confirmation required") { _ = try queued.rebased(snapshot:snapshot(),evidence:cancelled,confirmed:false) }
  check(try queued.rebased(snapshot:snapshot(title:"Aktuell"),evidence:cancelled,confirmed:true).state == .draft,"cancelled operation can rebase explicitly")
  let directory=FileManager.default.temporaryDirectory.appendingPathComponent("maengelfix-inspection-tests-\(UUID().uuidString)")
  try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true)
  defer { try? FileManager.default.removeItem(at:directory) }
  let url=directory.appendingPathComponent("owner.json")
  let archive=InspectionArchive(url:url,ownerID:owner)
  try await archive.save(draft,photos:[photoID:bytes],expectedRevision:nil)
  let reopened=InspectionArchive(url:url,ownerID:owner)
  check(try await reopened.load()==[draft],"cold reopen actual disk")
  check(try await reopened.photos(draftID:draftID)==[photoID:bytes],"batch read exact photo bytes")
  await rejectsAsync("stale revision") { try await reopened.save(draft,photos:[:],expectedRevision:nil) }
  var second=try fresh("88888888-8888-4888-8888-888888888888")
  try await archive.save(second,photos:[:],expectedRevision:nil)
  try await reopened.save(queued,photos:[:],expectedRevision:draft.revision)
  check(try await archive.load().count==2,"fresh reads preserve independent drafts")
  await rejectsAsync("ordinary save cannot unseal") { try await archive.save(draft,photos:[:],expectedRevision:queued.revision) }
  let before=try Data(contentsOf:url)
  second=try second.addingFinding(InspectionFinding(id:operationID,roomID:nil,title:"x",description:"y",category:"Sonstiges",severity:"normal"))
  await rejectsAsync("hash collision rollback") { try await archive.save(second,photos:[photoID:Data([1])],expectedRevision:0) }
  check(try Data(contentsOf:url)==before,"failed write preserves bytes")
  let wrong=InspectionArchive(url:url,ownerID:roomID)
  await rejectsAsync("wrong owner") { _ = try await wrong.load() }
  try Data("corrupt".utf8).write(to:url,options:.atomic)
  await rejectsAsync("corrupt preserved") { _ = try await archive.load() }
  check(try String(contentsOf:url,encoding:.utf8)=="corrupt","read never repairs corrupt archive")
  try await archive.purgeOwner()
  await rejectsAsync("deleted owner barrier") { try await reopened.save(try fresh(),photos:[:],expectedRevision:nil) }
  check(!String(data:try Data(contentsOf:url),encoding:.utf8)!.contains("Foto.png"),"purge removes corrupt/raw owner payload")
  if let target=ProcessInfo.processInfo.environment["MAENGELFIX_WIRE_FIXTURE"] { try Data(queued.batchPayload!.utf8).write(to:URL(fileURLWithPath:target),options:.atomic) }
  print("ALL \(checks) NATIVE INSPECTION OUTBOX CHECKS PASSED")
 }
}
