import Foundation

/// All instances share the same serial disk coordinator. No suspension occurs between
/// fresh read, revision validation and atomic replacement; another screen cannot overwrite it.
struct InspectionArchive: Sendable {
 let url:URL;let ownerID:String
 static func local(ownerID:String)throws->Self {
  _=try inspectionID(ownerID)
  let root=try FileManager.default.url(for:.applicationSupportDirectory,in:.userDomainMask,appropriateFor:nil,create:true).appendingPathComponent("MaengelFix/InspectionOutbox",isDirectory:true)
  return Self(url:root.appendingPathComponent(ownerID+".json"),ownerID:ownerID)
 }
 func load()async throws->[InspectionDraft]{try await InspectionArchiveCoordinator.shared.load(url,ownerID)}
 func photos(draftID:String)async throws->[String:Data]{try await InspectionArchiveCoordinator.shared.photos(url,ownerID,draftID)}
 func save(_ draft:InspectionDraft,photos:[String:Data],expectedRevision:Int?)async throws {try await InspectionArchiveCoordinator.shared.save(url,ownerID,draft,photos,expectedRevision)}
 func delete(draftID:String,expectedRevision:Int)async throws{try await InspectionArchiveCoordinator.shared.delete(url,ownerID,draftID,expectedRevision)}
 func rebase(draftID:String,expectedRevision:Int,snapshot:InspectionJSON,evidence:InspectionCancellation,confirmed:Bool)async throws{try await InspectionArchiveCoordinator.shared.rebase(url,ownerID,draftID,expectedRevision,snapshot,evidence,confirmed)}
 func purgeOwner()async throws{try await InspectionArchiveCoordinator.shared.purge(url,ownerID)}
}
private struct InspectionEnvelope: Codable {
 var schemaVersion=1;let ownerID:String;var deleted=false;var drafts:[InspectionDraft]=[];var photos:[String:Data]=[:]
}
private actor InspectionArchiveCoordinator {
 static let shared=InspectionArchiveCoordinator()
 private func read(_ url:URL,_ owner:String)throws->InspectionEnvelope {
  _=try inspectionID(owner)
  guard FileManager.default.fileExists(atPath:url.path)else{return InspectionEnvelope(ownerID:owner)}
  let attributes=try FileManager.default.attributesOfItem(atPath:url.path)
  try inspectionNeed(((attributes[.size] as? NSNumber)?.intValue ?? Int.max) <= 72*1024*1024,.capacity)
  let bytes=try Data(contentsOf:url,options:.mappedIfSafe)
  let raw:InspectionJSON
  do {raw=try InspectionJSON.parse(bytes)}catch{throw InspectionError.corrupt}
  guard let fields=raw.object else{throw InspectionError.corrupt}
  try inspectionNeed(Set(fields.keys)==Set(["schemaVersion","ownerID","deleted","drafts","photos"]),.corrupt)
  try inspectionNeed(raw["schemaVersion"] == .number(1),.future)
  try inspectionNeed(raw["ownerID"] == .string(owner),.identity)
  guard let records=raw["drafts"].array else{throw InspectionError.corrupt}
  let allowed=Set(["schemaVersion","id","ownerID","organizationID","protocolID","revision","createdAt","updatedAt","baseline","rooms","findings","photos","state","operationID","batchPayload","receipt"])
  for record in records{guard let object=record.object else{throw InspectionError.corrupt};try inspectionNeed(Set(object.keys).isSubset(of:allowed),.future)}
  let envelope:InspectionEnvelope
  do {envelope=try JSONDecoder().decode(InspectionEnvelope.self,from:bytes)}catch{throw InspectionError.corrupt}
  try inspectionNeed(!envelope.deleted,.deleted)
  try validate(envelope)
  return envelope
 }
 private func validate(_ envelope:InspectionEnvelope)throws {
  try inspectionNeed(envelope.drafts.count<=10,.capacity)
  var draftIDs=Set<String>(),photoIDs=Set<String>();var total=0
  for draft in envelope.drafts {
   try draft.validate();try inspectionNeed(draft.ownerID==envelope.ownerID,.identity);try inspectionNeed(draftIDs.insert(draft.id).inserted,.corrupt)
   for photo in draft.photos {
    try inspectionNeed(photoIDs.insert(photo.id).inserted,.corrupt)
    guard let bytes=envelope.photos[photo.id]else{throw InspectionError.corrupt}
    try inspectionNeed(bytes.count==photo.size && inspectionHash(bytes)==photo.sha256,.corrupt)
    try inspectionNeed(magic(bytes,photo.mime),.corrupt);total+=bytes.count
   }
  }
  try inspectionNeed(photoIDs==Set(envelope.photos.keys),.corrupt)
  try inspectionNeed(total<=50*1024*1024,.capacity)
 }
 private func magic(_ data:Data,_ mime:String)->Bool {
  let bytes=[UInt8](data.prefix(12))
  if mime=="image/png"{return bytes.count>=8 && Array(bytes.prefix(8))==[137,80,78,71,13,10,26,10]}
  if mime=="image/jpeg"{return bytes.count>=3 && Array(bytes.prefix(3))==[255,216,255]}
  return mime=="image/webp" && bytes.count>=12 && String(bytes:bytes[0..<4],encoding:.ascii)=="RIFF" && String(bytes:bytes[8..<12],encoding:.ascii)=="WEBP"
 }
 private func write(_ value:InspectionEnvelope,_ url:URL)throws {
  if !value.deleted {try validate(value)}
  let bytes=try JSONEncoder().encode(value);try inspectionNeed(bytes.count<=72*1024*1024,.capacity)
  try FileManager.default.createDirectory(at:url.deletingLastPathComponent(),withIntermediateDirectories:true)
  try bytes.write(to:url,options:[.atomic,.completeFileProtectionUnlessOpen])
 }
 func load(_ url:URL,_ owner:String)throws->[InspectionDraft]{try read(url,owner).drafts}
 func photos(_ url:URL,_ owner:String,_ draftID:String)throws->[String:Data]{let envelope=try read(url,owner);guard let draft=envelope.drafts.first(where:{$0.id==draftID})else{throw InspectionError.identity};return Dictionary(uniqueKeysWithValues:draft.photos.map{($0.id,envelope.photos[$0.id]!)})}
 func save(_ url:URL,_ owner:String,_ draft:InspectionDraft,_ photos:[String:Data],_ expected:Int?)throws {
  var envelope=try read(url,owner);try draft.validate();try inspectionNeed(draft.ownerID==owner,.identity)
  let index=envelope.drafts.firstIndex{$0.id==draft.id};let previous=index.map{envelope.drafts[$0]}
  try inspectionNeed(previous?.revision==expected,.conflict)
  if let old=previous {
   try inspectionNeed((draft.revision>old.revision || draft==old) && draft.createdAt==old.createdAt && draft.protocolID==old.protocolID && draft.organizationID==old.organizationID,.conflict)
   if old.state != .draft {try inspectionNeed(draft.batchPayload==old.batchPayload && draft.operationID==old.operationID && draft.state != .draft,.conflict);if old.state == .acknowledged{try inspectionNeed(draft==old,.conflict)}}
  }
  let allowed=Set(draft.photos.map(\.id));try inspectionNeed(Set(photos.keys).isSubset(of:allowed),.corrupt)
  for (id,bytes) in photos {if let old=envelope.photos[id]{try inspectionNeed(old==bytes,.corrupt)};envelope.photos[id]=bytes}
  if let index{envelope.drafts[index]=draft}else{envelope.drafts.append(draft)}
  prune(&envelope);try write(envelope,url)
 }
 private func prune(_ envelope:inout InspectionEnvelope){let ids=Set(envelope.drafts.flatMap{$0.photos.map(\.id)});envelope.photos=envelope.photos.filter{ids.contains($0.key)}}
 func delete(_ url:URL,_ owner:String,_ id:String,_ expected:Int)throws {var envelope=try read(url,owner);guard let index=envelope.drafts.firstIndex(where:{$0.id==id})else{throw InspectionError.conflict};try inspectionNeed(envelope.drafts[index].revision==expected && envelope.drafts[index].state != .queued,.conflict);envelope.drafts.remove(at:index);prune(&envelope);try write(envelope,url)}
 func rebase(_ url:URL,_ owner:String,_ id:String,_ expected:Int,_ snapshot:InspectionJSON,_ evidence:InspectionCancellation,_ confirmed:Bool)throws{var envelope=try read(url,owner);guard let index=envelope.drafts.firstIndex(where:{$0.id==id})else{throw InspectionError.conflict};try inspectionNeed(envelope.drafts[index].revision==expected,.conflict);envelope.drafts[index]=try envelope.drafts[index].rebased(snapshot:snapshot,evidence:evidence,confirmed:confirmed);try write(envelope,url)}
 func purge(_ url:URL,_ owner:String)throws {
  // Deliberately do not decode corrupt photos/envelopes. The path is derived only from
  // the authenticated owner; tombstone and removed payload are one atomic replacement.
  _=try inspectionID(owner);var envelope=InspectionEnvelope(ownerID:owner);envelope.deleted=true;try write(envelope,url)
 }
}
