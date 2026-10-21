import Foundation
import CoreFoundation
import CryptoKit

enum InspectionError: String, Error, LocalizedError { case invalid, identity, capacity, conflict, corrupt, future, deleted, uncertain
 var errorDescription: String? { switch self {
 case .invalid: return "Bitte prüfe Pflichtfelder und Formate. / Check required fields and formats."
 case .identity: return "Anmeldung oder Zuordnung stimmt nicht überein. / Account or scope mismatch."
 case .capacity: return "Höchstgrenze erreicht. / Capacity limit reached."
 case .conflict: return "Der gespeicherte Stand hat sich geändert. / The saved record changed."
 case .corrupt: return "Lokale Daten konnten nicht sicher gelesen werden; sie bleiben erhalten. / Local data could not be read safely and is retained."
 case .future: return "Unbekanntes Speicherformat; Daten bleiben erhalten. / Unknown storage format; data is retained."
 case .deleted: return "Lokaler Speicher dieses gelöschten Kontos ist gesperrt. / Local storage for this deleted account is blocked."
 case .uncertain: return "Übertragung unklar. Prüfe denselben Ausgang erneut. / Upload outcome unknown. Check the same outbox again."
 } }
}
func inspectionNeed(_ condition: Bool, _ error: InspectionError = .invalid) throws { if !condition { throw error } }
func inspectionID(_ value: String) throws -> String { try inspectionNeed(UUID(uuidString:value) != nil && value.count == 36 && value == value.lowercased(),.identity); return value }
func inspectionText(_ value: String, _ limit: Int, required: Bool = false) throws { try inspectionNeed(value.unicodeScalars.count<=limit && (!required || !value.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)) }
func inspectionHash(_ data: Data) -> String { SHA256.hash(data:data).map { String(format:"%02x",$0) }.joined() }

indirect enum InspectionJSON: Codable, Equatable, Sendable {
 case object([String:InspectionJSON]), array([InspectionJSON]), string(String), number(Int64), bool(Bool), null
 init(from decoder: Decoder) throws { let c=try decoder.singleValueContainer(); if c.decodeNil(){self = .null} else if let v=try? c.decode(Bool.self){self = .bool(v)} else if let v=try? c.decode(Int64.self){try inspectionNeed(v >= -9_007_199_254_740_991 && v <= 9_007_199_254_740_991);self = .number(v)} else if let v=try? c.decode(String.self){self = .string(v)} else if let v=try? c.decode([InspectionJSON].self){self = .array(v)} else {self = .object(try c.decode([String:InspectionJSON].self))} }
 func encode(to encoder: Encoder) throws { var c=encoder.singleValueContainer();switch self {case .null:try c.encodeNil();case .object(let v):try c.encode(v);case .array(let v):try c.encode(v);case .string(let v):try c.encode(v);case .number(let v):try c.encode(v);case .bool(let v):try c.encode(v)} }
 static func parse(_ data: Data) throws -> Self {
  try inspectionNeed(data.count<=72*1024*1024,.capacity)
  func convert(_ value: Any) throws -> Self { if value is NSNull{return .null}; if let n=value as? NSNumber { if CFGetTypeID(n)==CFBooleanGetTypeID(){return .bool(n.boolValue)};let d=n.doubleValue;try inspectionNeed(d.isFinite && d.rounded()==d && abs(d)<=9_007_199_254_740_991);return .number(n.int64Value) };if let s=value as? String{return .string(s)};if let a=value as? [Any]{return .array(try a.map(convert))};if let o=value as? [String:Any]{return .object(try o.mapValues(convert))};throw InspectionError.invalid }
  return try convert(JSONSerialization.jsonObject(with:data,options:[.fragmentsAllowed]))
 }
 static func encoded<T:Encodable>(_ value:T) throws -> Self { try parse(JSONEncoder().encode(value)) }
 var object: [String:Self]? { if case .object(let v)=self{return v};return nil }
 var array: [Self]? { if case .array(let v)=self{return v};return nil }
 var string: String? { if case .string(let v)=self{return v};return nil }
 var integer: Int? { if case .number(let v)=self{return Int(exactly:v)};return nil }
 var boolean: Bool? { if case .bool(let v)=self{return v};return nil }
 subscript(_ key:String)->Self { object?[key] ?? .null }
 static func quoted(_ value:String)->String { var result="\"";for s in value.unicodeScalars { switch s.value {case 34:result+="\\\"";case 92:result+="\\\\";case 8:result+="\\b";case 9:result+="\\t";case 10:result+="\\n";case 12:result+="\\f";case 13:result+="\\r";case 0..<32:result+=String(format:"\\u%04x",s.value);default:result+=String(s)} };return result+"\"" }
 var canonical:String { switch self {case .null:return "null";case .bool(let v):return v ? "true":"false";case .number(let v):return String(v);case .string(let v):return Self.quoted(v);case .array(let v):return "["+v.map(\.canonical).joined(separator:",")+"]";case .object(let v):return "{"+v.keys.sorted().map{Self.quoted($0)+":"+v[$0]!.canonical}.joined(separator:",")+"}"} }
}
struct InspectionRoom: Codable, Equatable, Identifiable, Sendable { let id:String; var name:String;var condition:String;var notes:String }
struct InspectionFinding: Codable, Equatable, Identifiable, Sendable { let id:String;var roomID:String?;var title:String;var description:String;var category:String;var severity:String
 enum CodingKeys:String,CodingKey {case id,roomID,title,description,category,severity}
 func encode(to encoder:Encoder)throws{var c=encoder.container(keyedBy:CodingKeys.self);try c.encode(id,forKey:.id);try c.encode(roomID,forKey:.roomID);try c.encode(title,forKey:.title);try c.encode(description,forKey:.description);try c.encode(category,forKey:.category);try c.encode(severity,forKey:.severity)}
}
struct InspectionPhoto: Codable, Equatable, Identifiable, Sendable {
 let id:String,findingID:String,name:String,mime:String;let size:Int;let sha256:String
 init(id:String,findingID:String,name:String,mime:String,data:Data)throws {self.id=try inspectionID(id);self.findingID=try inspectionID(findingID);self.name=name;self.mime=mime;size=data.count;sha256=inspectionHash(data);try validate()}
 func validate()throws { _=try inspectionID(id);_=try inspectionID(findingID);try inspectionText(name,250,required:true);try inspectionNeed(["image/jpeg","image/png","image/webp"].contains(mime));try inspectionNeed(size>0 && size<=3*1024*1024,.capacity);try inspectionNeed(sha256.count==64 && sha256.allSatisfy{"0123456789abcdef".contains($0)}) }
}
struct InspectionReceipt: Codable, Equatable, Sendable { let operationID:String,protocolID:String,ownerID:String,payload:String;let result:InspectionJSON }
struct InspectionCancellation: Sendable { let ownerID:String,protocolID:String,operationID:String,payload:String;let cancelled:Bool }
struct InspectionDraft: Codable, Equatable, Identifiable, Sendable {
 enum State:String,Codable,Sendable { case draft,queued,acknowledged }
 let schemaVersion:Int;let id:String,ownerID:String;let organizationID:String?;let protocolID:String
 var revision:Int;let createdAt:String;var updatedAt:String;var baseline:InspectionJSON;var rooms:[InspectionRoom];var findings:[InspectionFinding];var photos:[InspectionPhoto];var state:State;var operationID:String?;var batchPayload:String?;var receipt:InspectionReceipt?
 static func normalized(_ source:InspectionJSON)throws->InspectionJSON {
  guard let root=source.object,Set(root.keys)==Set(["protocol","rooms","findings"]),var protocolValue=root["protocol"]?.object,let rooms=root["rooms"]?.array,let findings=root["findings"]?.array else{throw InspectionError.invalid}
  let protocolFields=["id","organization_id","property_id","unit_id","created_by","protocol_type","status","title","inspection_at","tenant_name","tenant_email","general_notes","completed_at","created_at","updated_at"]
  let display=["property_name","property_street","property_postal_code","property_city","unit_label","unit_floor"]
  try inspectionNeed(Set(protocolValue.keys).isSubset(of:Set(protocolFields+display)) && protocolValue["organization_id"] != nil)
  guard let pid=source["protocol"]["id"].string,let title=source["protocol"]["title"].string,let update=source["protocol"]["updated_at"].string else{throw InspectionError.invalid}
  _=try inspectionID(pid);if source["protocol"]["organization_id"] != .null {guard let org=source["protocol"]["organization_id"].string else{throw InspectionError.identity};_=try inspectionID(org)}
  try inspectionText(title,180,required:true);try inspectionText(update,100,required:true);try inspectionNeed(["draft","completed"].contains(source["protocol"]["status"].string ?? ""));try inspectionNeed(rooms.count<=1000 && findings.count<=1000,.capacity)
  var roomIDs=Set<String>(),findingIDs=Set<String>()
  for room in rooms {guard let r=room.object,let id=room["id"].string,let name=room["name"].string else{throw InspectionError.invalid};try inspectionNeed(Set(r.keys).isSubset(of:Set(["id","protocol_id","name","position","condition","notes","created_at"])) && r["notes"] != nil);_=try inspectionID(id);try inspectionNeed(roomIDs.insert(id).inserted);try inspectionText(name,120,required:true);try inspectionNeed(["ok","notice","defect"].contains(room["condition"].string ?? ""));if room["notes"] != .null{guard let text=room["notes"].string else{throw InspectionError.invalid};try inspectionText(text,1200)};if let linked=r["protocol_id"]{try inspectionNeed(linked == .string(pid),.identity)} }
  var normalizedFindings:[InspectionJSON]=[]
  for finding in findings {guard var f=finding.object,let id=finding["id"].string else{throw InspectionError.invalid};try inspectionNeed(Set(f.keys).isSubset(of:Set(["id","protocol_id","room_id","created_by","title","description","category","severity","status","defect_case_id","created_at","updated_at","room_name","attachment_count"])) && f["room_id"] != nil);_=try inspectionID(id);try inspectionNeed(findingIDs.insert(id).inserted);if finding["room_id"] != .null{try inspectionNeed(roomIDs.contains(finding["room_id"].string ?? ""),.identity)};for (key,max) in [("title",180),("description",3000),("category",80),("status",80)]{guard let value=finding[key].string else{throw InspectionError.invalid};try inspectionText(value,max,required:true)};try inspectionNeed(["minor","normal","urgent"].contains(finding["severity"].string ?? ""));try inspectionNeed((finding["attachment_count"].integer ?? -1)>=0);if let linked=f["protocol_id"]{try inspectionNeed(linked == .string(pid),.identity)};f.removeValue(forKey:"room_name");normalizedFindings.append(.object(f)) }
  try inspectionNeed(source.canonical.utf8.count<=1024*1024,.capacity);for field in display{protocolValue.removeValue(forKey:field)}
  return .object(["protocol":.object(protocolValue),"rooms":.array(rooms),"findings":.array(normalizedFindings)])
 }
 static func validTime(_ value:String)throws {let f=ISO8601DateFormatter();f.formatOptions=[.withInternetDateTime,.withFractionalSeconds];try inspectionNeed(f.date(from:value).map{f.string(from:$0)==value} ?? false)}
 static func create(id:String,ownerID:String,organizationID:String?,snapshot:InspectionJSON,at:String)throws->Self {
  let source=try normalized(snapshot);try inspectionNeed(source["protocol"]["status"] == .string("draft"),.conflict)
  let value=Self(schemaVersion:1,id:try inspectionID(id),ownerID:try inspectionID(ownerID),organizationID:organizationID,protocolID:source["protocol"]["id"].string!,revision:0,createdAt:at,updatedAt:at,baseline:source,rooms:[],findings:[],photos:[],state:.draft,operationID:nil,batchPayload:nil,receipt:nil);try value.validate();return value
 }
 func validate()throws {
  try inspectionNeed(schemaVersion==1,.future);_=try inspectionID(id);_=try inspectionID(ownerID);_=try inspectionID(protocolID);if let organizationID{_=try inspectionID(organizationID)};try inspectionNeed(revision>=0);try Self.validTime(createdAt);try Self.validTime(updatedAt);try inspectionNeed(updatedAt>=createdAt);try inspectionNeed(try Self.normalized(baseline)==baseline);try inspectionNeed(baseline["protocol"]["id"] == .string(protocolID) && baseline["protocol"]["organization_id"] == (organizationID.map(InspectionJSON.string) ?? .null),.identity)
  try inspectionNeed(rooms.count<=20 && findings.count<=50 && photos.count<=250,.capacity)
  var all=Set([id]);var roomIDs=Set((baseline["rooms"].array ?? []).compactMap{$0["id"].string});let oldFindings=Set((baseline["findings"].array ?? []).compactMap{$0["id"].string})
  for room in rooms {_=try inspectionID(room.id);try inspectionNeed(!roomIDs.contains(room.id) && all.insert(room.id).inserted);roomIDs.insert(room.id);try inspectionText(room.name,120,required:true);try inspectionNeed(room.name==room.name.trimmingCharacters(in:.whitespacesAndNewlines));try inspectionText(room.notes,1200);try inspectionNeed(["ok","notice","defect"].contains(room.condition))}
  for finding in findings {_=try inspectionID(finding.id);try inspectionNeed(all.insert(finding.id).inserted && !oldFindings.contains(finding.id));if let room=finding.roomID{try inspectionNeed(roomIDs.contains(room),.identity)};try inspectionText(finding.title,180,required:true);try inspectionNeed(finding.title==finding.title.trimmingCharacters(in:.whitespacesAndNewlines));try inspectionText(finding.description,3000,required:true);try inspectionText(finding.category,80,required:true);try inspectionNeed(["minor","normal","urgent"].contains(finding.severity))}
  let findingIDs=Set(findings.map(\.id));var total=0;for photo in photos{try photo.validate();try inspectionNeed(findingIDs.contains(photo.findingID),.identity);try inspectionNeed(all.insert(photo.id).inserted);total+=photo.size};try inspectionNeed(total<=20*1024*1024 && findings.allSatisfy{f in photos.filter{$0.findingID==f.id}.count<=5},.capacity)
  if state == .draft {try inspectionNeed(operationID==nil && batchPayload==nil && receipt==nil)}else{guard let operationID,let batchPayload else{throw InspectionError.invalid};_=try inspectionID(operationID);try inspectionNeed(!rooms.isEmpty || !findings.isEmpty);try inspectionNeed(batchPayload == (try payload(operationID)));if state == .queued{try inspectionNeed(receipt==nil)}else{guard let receipt else{throw InspectionError.invalid};try validateReceipt(receipt)}}
  try inspectionNeed(try InspectionJSON.encoded(self).canonical.utf8.count<=3*1024*1024,.capacity)
 }
 func payload(_ operationID:String)throws->String {try InspectionJSON.object(["version":.number(1),"operationID":.string(operationID),"protocolID":.string(protocolID),"organizationID":organizationID.map(InspectionJSON.string) ?? .null,"baseline":baseline,"rooms":InspectionJSON.encoded(rooms),"findings":InspectionJSON.encoded(findings),"photos":InspectionJSON.encoded(photos)]).canonical}
 func changed(_ action:(inout Self)->Void)throws->Self{try validate();try inspectionNeed(state == .draft,.conflict);var next=self;action(&next);next.revision+=1;try next.validate();return next}
 func addingRoom(_ room:InspectionRoom)throws->Self{var room=room;room.name=room.name.trimmingCharacters(in:.whitespacesAndNewlines);return try changed{$0.rooms.append(room)}}
 func addingFinding(_ finding:InspectionFinding)throws->Self{var finding=finding;finding.title=finding.title.trimmingCharacters(in:.whitespacesAndNewlines);return try changed{$0.findings.append(finding)}}
 func addingPhoto(_ photo:InspectionPhoto)throws->Self{try changed{$0.photos.append(photo)}}
 func sealed(operationID:String,at:String)throws->Self{try validate();try inspectionNeed(state == .draft && baseline["protocol"]["status"] == .string("draft"),.conflict);_=try inspectionID(operationID);try Self.validTime(at);try inspectionNeed(at>=updatedAt);var next=self;next.operationID=operationID;next.batchPayload=try payload(operationID);next.state = .queued;next.updatedAt=at;next.revision+=1;try next.validate();return next}
 func validateReceipt(_ value:InspectionReceipt)throws {try inspectionNeed(value.ownerID==ownerID && value.protocolID==protocolID && value.operationID==operationID && value.payload==batchPayload,.identity);guard let result=value.result.object else{throw InspectionError.invalid};try inspectionNeed(Set(result.keys)==Set(["rooms","findings","photos"]));for (key,ids) in [("rooms",rooms.map(\.id)),("findings",findings.map(\.id)),("photos",photos.map(\.id))]{guard let map=result[key]?.object else{throw InspectionError.invalid};try inspectionNeed(Set(map.keys)==Set(ids));let values=map.values.compactMap(\.string);try inspectionNeed(values.count==ids.count && Set(values).count==ids.count);for v in values{try inspectionText(v,120,required:true)}}}
 func acknowledged(_ value:InspectionReceipt)throws->Self{try validate();try inspectionNeed(state != .draft,.conflict);try validateReceipt(value);if state == .acknowledged{try inspectionNeed(receipt==value,.conflict);return self};var next=self;next.receipt=value;next.state = .acknowledged;next.revision+=1;try next.validate();return next}
 func rebased(snapshot:InspectionJSON,evidence:InspectionCancellation,confirmed:Bool)throws->Self{try validate();try inspectionNeed(state == .queued && confirmed && evidence.cancelled,.conflict);try inspectionNeed(evidence.ownerID==ownerID && evidence.protocolID==protocolID && evidence.operationID==operationID && evidence.payload==batchPayload,.identity);let source=try Self.normalized(snapshot);try inspectionNeed(source["protocol"]["status"] == .string("draft"),.conflict);var next=self;next.baseline=source;next.operationID=nil;next.batchPayload=nil;next.receipt=nil;next.state = .draft;next.revision+=1;try next.validate();return next}
}
