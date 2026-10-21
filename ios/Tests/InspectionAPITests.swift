import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

final class InspectionStub:URLProtocol,@unchecked Sendable {
 static var requests:[URLRequest]=[]
 static var handler:((URLRequest)throws->(Int,Data))!
 override class func canInit(with request:URLRequest)->Bool{true}
 override class func canonicalRequest(for request:URLRequest)->URLRequest{request}
 override func startLoading(){do{
  var captured=request
  if captured.httpBody == nil,let stream=captured.httpBodyStream {
   stream.open();defer{stream.close()}
   var bytes=Data();var buffer=[UInt8](repeating:0,count:4096)
   while true{let read=stream.read(&buffer,maxLength:buffer.count);if read<0{throw stream.streamError ?? InspectionError.invalid};if read==0{break};bytes.append(buffer,count:read)}
   captured.httpBody=bytes
   print("STUB captured httpBodyStream \(captured.httpMethod ?? "GET") \(captured.url?.path ?? "") bytes=\(bytes.count)")
  } else {print("STUB captured httpBody \(captured.httpMethod ?? "GET") \(captured.url?.path ?? "") bytes=\(captured.httpBody?.count ?? 0)")}
  Self.requests.append(captured);let (status,data)=try Self.handler(captured)
  client?.urlProtocol(self,didReceive:HTTPURLResponse(url:request.url!,statusCode:status,httpVersion:nil,headerFields:["Content-Type":"application/json"])!,cacheStoragePolicy:.notAllowed)
  client?.urlProtocol(self,didLoad:data);client?.urlProtocolDidFinishLoading(self)
 }catch{client?.urlProtocol(self,didFailWithError:error)}}
 override func stopLoading(){}
}
@main struct InspectionAPITests {
 @MainActor static func main()async throws {
  var count=0
  func check(_ value:Bool,_ name:String){count+=1;if !value{fatalError("FAIL \(name)")}}
  let config=URLSessionConfiguration.ephemeral;config.protocolClasses=[InspectionStub.self]
  let api=APIClient(baseURL:URL(string:"https://fixture.invalid")!,session:URLSession(configuration:config))
  let owner="11111111-1111-4111-8111-111111111111",pid="22222222-2222-4222-8222-222222222222",rid="44444444-4444-4444-8444-444444444444"
  let source=try InspectionJSON.parse(Data("""
  {"protocol":{"id":"\(pid)","organization_id":null,"title":"Ä / 🔧","status":"draft","updated_at":"2026-10-21T10:00:00.000Z"},"rooms":[],"findings":[]}
  """.utf8))
  var current=true
  InspectionStub.handler={request in (200,Data(source.canonical.utf8))}
  let detail=try await api.inspectionDetail(id:pid,current:{current})
  check(detail["protocol"]["organization_id"] == .null && detail["protocol"]["updated_at"].string != nil,"raw snake_case baseline preserved")
  check(InspectionStub.requests.last?.url?.path=="/api/inspections/\(pid)","detail exact authorized path")
  _=try await api.inspectionList(current:{current})
  check(InspectionStub.requests.last?.url?.path=="/api/inspections","list existing endpoint")
  _=try await api.inspectionProperties(current:{current})
  check(InspectionStub.requests.last?.url?.path=="/api/properties","property existing endpoint")
  _=try await api.inspectionProperty(id:rid,current:{current})
  check(InspectionStub.requests.last?.url?.path=="/api/properties/\(rid)","unit scope endpoint")
  let input=InspectionJSON.object(["title":.string("QA"),"protocolType":.string("handover")])
  _=try await api.inspectionCreate(input,current:{current})
  check(InspectionStub.requests.last?.httpMethod=="POST" && InspectionStub.requests.last?.httpBody==Data(input.canonical.utf8),"explicit creation exact body")
  let before=InspectionStub.requests.count;current=false
  do{_=try await api.inspectionDetail(id:pid,current:{current});fatalError("FAIL stale account sent request")}catch{check(InspectionStub.requests.count==before,"stale account stops before request")}
  current=true
  InspectionStub.handler={request in current=false;return (200,Data(source.canonical.utf8))}
  do{_=try await api.inspectionDetail(id:pid,current:{current});fatalError("FAIL stale response accepted")}catch{check(true,"account changed while awaiting rejected")}
  current=true
  InspectionStub.handler={_ in (402,Data(#"{"error":"Plan required"}"#.utf8))}
  do{_=try await api.inspectionList(current:{current});fatalError("FAIL plan response ignored")}catch{check((error as? APIError)?.localizedDescription=="Plan required","original server gate surfaced")}
  var draft=try InspectionDraft.create(id:"33333333-3333-4333-8333-333333333333",ownerID:owner,organizationID:nil,snapshot:source,at:"2026-10-21T10:00:00.000Z")
  draft=try draft.addingRoom(InspectionRoom(id:rid,name:"Küche",condition:"ok",notes:""))
  draft=try draft.sealed(operationID:"77777777-7777-4777-8777-777777777777",at:draft.updatedAt)
  let result:InspectionJSON = .object(["rooms":.object([rid:.string("server-room")]),"findings":.object([:]),"photos":.object([:])])
  let receipt=InspectionReceipt(operationID:draft.operationID!,protocolID:pid,ownerID:owner,payload:draft.batchPayload!,result:result)
  InspectionStub.handler={_ in (200,Data(try InspectionJSON.encoded(["receipt":receipt]).canonical.utf8))}
  let returned=try await api.inspectionPublish(draft,photos:[:],current:{current})
  check(returned==receipt,"matching publish receipt")
  let request=InspectionStub.requests.last!
  guard let body=request.httpBody else{fatalError("FAIL stub captured no actual multipart bytes") }
  check(request.url?.path=="/api/inspections/\(pid)/offline-batches" && request.httpMethod=="POST","batch exact endpoint")
  check(request.value(forHTTPHeaderField:"Content-Length")==String(body.count),"known bounded multipart length")
  check(String(data:body,encoding:.utf8)?.contains(draft.batchPayload!)==true,"canonical body sent without rewriting")
  InspectionStub.handler={request in let hash=inspectionHash(Data(draft.batchPayload!.utf8));return (200,Data(InspectionJSON.object(["exists":.bool(false),"cancelled":.bool(true),"ownerID":.string(owner),"protocolID":.string(pid),"operationID":.string(draft.operationID!),"payloadHash":.string(hash)]).canonical.utf8))}
  let outcome=try await api.inspectionOutcome(draft,cancel:true,current:{current})
  check(outcome["cancelled"] == .bool(true) && outcome["payload"] == .string(draft.batchPayload!),"cancellation exact proof binds payload")
  check(InspectionStub.requests.last?.url?.path.hasSuffix("/cancel")==true && InspectionStub.requests.last?.httpMethod=="POST","explicit cancellation endpoint")
  print("ALL \(count) NATIVE INSPECTION API CHECKS PASSED")
 }
}
