import SwiftUI
import PhotosUI
import UIKit
import ImageIO

@MainActor struct InspectionOutboxView:View {
 @Environment(AppSession.self) private var session
 @Environment(\.dismiss) private var dismiss
 let ownerID:String,initialSnapshot:InspectionJSON,language:String
 @State private var drafts:[InspectionDraft]=[]
 @State private var selectedID=""
 @State private var gallery:[String:Data]=[:]
 @State private var room=InspectionRoom(id:UUID().uuidString.lowercased(),name:"",condition:"ok",notes:"")
 @State private var roomBase:InspectionRoom?
 @State private var roomEdit:String?
 @State private var finding=InspectionFinding(id:UUID().uuidString.lowercased(),roomID:nil,title:"",description:"",category:"Sonstiges",severity:"normal")
 @State private var findingBase:InspectionFinding?
 @State private var findingEdit:String?
 @State private var pendingImages:[DraftImage]=[]
 @State private var photoTarget:String?
 @State private var cameraTarget:String?
 @State private var showCamera=false
 @State private var busy=false
 @State private var blocked=false
 @State private var alive=true
 @State private var loadingImages=false
 @State private var error:String?
 @State private var showDiscard=false
 @State private var deleting:InspectionDraft?
 @State private var nextAction:(()->Void)?
 @State private var review:InspectionJSON?
 @State private var confirmed=false
 private var protocolID:String{initialSnapshot["protocol"]["id"].string ?? ""}
 private var current:Bool{alive && session.phase == .signedIn && session.user?.id==ownerID}
 private var draft:InspectionDraft?{drafts.first{$0.id==selectedID}}
 private var editable:Bool{draft?.state == .draft && !busy && !blocked && current}
 private var roomDirty:Bool{if let base=roomBase{return room != base};return !room.name.isEmpty || room.condition != "ok" || !room.notes.isEmpty}
 private var findingDirty:Bool{if let base=findingBase{return finding != base};return finding.roomID != nil || !finding.title.isEmpty || !finding.description.isEmpty || finding.category != "Sonstiges" || finding.severity != "normal"}
 private var dirty:Bool{roomDirty || findingDirty || !pendingImages.isEmpty}
 private func l(_ de:String,_ en:String)->String{inspectionLabel(language,de,en)}
 private func archive()throws->InspectionArchive{try .local(ownerID:ownerID)}
 var body:some View {
  NavigationStack{Form{
   Section{Text(initialSnapshot["protocol"]["title"].string ?? "").font(.headline);Text(l("Neue Ergänzungen bleiben lokal bis zur ausdrücklichen Übertragung. Nach dem Öffnen kannst du offline weiter erfassen; erneutes Öffnen nach Neustart braucht Online-Zugriff.","New additions stay local until explicitly published. After opening you can capture offline; reopening after restart requires online access."));Text(l("Keine automatischen Nachrichten, Mängel oder Protokollabschlüsse. Fotos: JPEG/PNG/WebP, 3 MB je Foto, 5 je Feststellung, 20 MB je Entwurf; 10 Entwürfe/50 MB je Konto.","No automatic messages, cases or inspection completion. Photos: JPEG/PNG/WebP, 3 MB each, 5 per finding, 20 MB per draft; 10 drafts/50 MB per account.")).font(.caption)}
   if !current{Text(l("Anmeldung oder Zugriff nicht mehr verfügbar. Schließe die Ansicht.","Account or access is no longer available. Close this view.")).foregroundStyle(.red)}
   if let error{Section{Text(error).foregroundStyle(.red)}}
   if busy || loadingImages{ProgressView()}
   if blocked{Section{Text(l("Speichern bleibt gesperrt. Vorhandene Daten werden nicht ersetzt.","Saving is blocked. Existing data is not replaced."));Button(l("Erneut laden","Reload")){Task{await reload()}}.disabled(busy)}}
   Section{
    Button(l("Neuen lokalen Entwurf speichern","Save a new local draft")){guardChange{Task{await newDraft()}}}.disabled(busy || blocked || !current || initialSnapshot["protocol"]["status"] != .string("draft"))
    if !drafts.isEmpty{Picker(l("Gespeicherter Ausgang","Saved outbox"),selection:Binding(get:{selectedID},set:{next in guard next != selectedID else{return};guardChange{clearForms();selectedID=next;Task{await loadGallery()}}})){ForEach(drafts){value in Text("\(value.createdAt) · \(value.rooms.count)/\(value.findings.count) · \(stateLabel(value.state))").tag(value.id)}}.disabled(busy)}
   }
   if let draft{
    Section{Text(stateLabel(draft.state)).font(.headline);Text("\(draft.rooms.count) "+l("neue Räume","new rooms")+" · \(draft.findings.count) "+l("neue Feststellungen","new findings")+" · \(draft.photos.count) "+l("Fotos","photos"))}
    if editable{roomForm;findingForm}
    ForEach(draft.rooms){value in Section(value.name){Text(inspectionCondition(value.condition,language));Text(value.notes);if editable{Button(l("Raum bearbeiten","Edit room")){if roomEdit != value.id{guardChange{clearForms();room=value;roomBase=value;roomEdit=value.id}}};Button(l("Lokalen Raum entfernen","Remove local room"),role:.destructive){guardChange{Task{_ = await run{let next=try draft.changed{$0.rooms.removeAll{$0.id==value.id}};try await archive().save(next,photos:[:],expectedRevision:draft.revision)}}}}.disabled(draft.findings.contains{$0.roomID==value.id})}}}
    ForEach(draft.findings){value in findingSection(value,draft)}
    if !pendingImages.isEmpty{Section(l("Noch nicht gespeicherte Fotoauswahl","Unsaved photo selection")){DraftImageStrip(images:pendingImages){id in pendingImages.removeAll{$0.id==id}};Button(l("Dieselben Fotos erneut speichern","Retry the same photos")){Task{await savePhotos()}}.disabled(busy);Button(l("Auswahl verwerfen","Discard selection"),role:.destructive){pendingImages=[];photoTarget=nil}.disabled(busy)}}
    if draft.state == .draft {Section{Button(l("Gespeicherten Entwurf festschreiben","Seal saved draft")){guardChange{Task{await seal(draft)}}}.disabled(busy || blocked || (draft.rooms.isEmpty && draft.findings.isEmpty))}}
    if draft.state == .queued {queuedSection(draft)}
    if draft.state == .acknowledged{Section{Text(l("Eine passende Serverbestätigung bestätigt die Übernahme. Server-PDF und ausdrückliche Übernahme als Mangel findest du im bestehenden Protokoll.","A matching server receipt confirms the additions. Open the existing inspection for its server PDF and explicit case conversion."))}}
    if draft.state != .queued{Section{Button(l("Nur diesen lokalen Datensatz löschen","Delete only this local record"),role:.destructive){guardChange{deleting=draft}}.disabled(busy || blocked)}}
   }
  }.disabled(busy || loadingImages || !current).scrollDismissesKeyboard(.interactively).navigationTitle(l("Lokaler Ausgang","Local outbox"))
   .toolbar{ToolbarItem(placement:.cancellationAction){Button(l("Schließen","Close")){guardChange{dismiss()}}.disabled(busy || loadingImages)}}
   .confirmationDialog(l("Nicht gespeicherte Eingaben verwerfen? Gespeicherte Entwürfe bleiben erhalten.","Discard unsaved input? Saved drafts are kept."),isPresented:$showDiscard,titleVisibility:.visible){Button(l("Verwerfen","Discard"),role:.destructive){let action=nextAction;nextAction=nil;action?()};Button(l("Abbrechen","Cancel"),role:.cancel){nextAction=nil}}
   .alert(l("Lokalen Entwurf und Fotos löschen? Serverdaten bleiben bestehen.","Delete the local draft and photos? Server records are kept."),isPresented:Binding(get:{deleting != nil},set:{if !$0{deleting=nil}})){Button(l("Löschen","Delete"),role:.destructive){if let value=deleting{deleting=nil;Task{let success=await run{try await archive().delete(draftID:value.id,expectedRevision:value.revision)};if success{clearForms()}}}};Button(l("Abbrechen","Cancel"),role:.cancel){deleting=nil}}
   .sheet(isPresented:$showCamera){CameraPicker{image in guard current,let target=cameraTarget else{return};do{let photo=try inspectionJPEG(image:image);guardPhotos(target,[photo])}catch{self.error=error.localizedDescription}}.ignoresSafeArea()}
   .task{alive=true;await reload()}
   .onDisappear{alive=false}
  }.interactiveDismissDisabled(dirty || busy || loadingImages)
 }
 private var roomForm:some View {Section(roomEdit == nil ? l("Neuer Raum","New room"):l("Raum bearbeiten","Edit room")){
  TextField(l("Name","Name"),text:$room.name)
  Picker(l("Zustand","Condition"),selection:$room.condition){ForEach(["ok","notice","defect"],id:\.self){value in Text(inspectionCondition(value,language)).tag(value)}}
  TextField(l("Notiz","Note"),text:$room.notes,axis:.vertical).lineLimit(3...8)
  Button(l("Raum lokal speichern","Save room locally")){Task{await saveRoom()}}.disabled(!validRoom)
  if roomEdit != nil{Button(l("Bearbeitung abbrechen","Cancel editing")){guardChange{clearRoom()}}}
 }}
 private var findingForm:some View {Section(findingEdit == nil ? l("Neue Feststellung","New finding"):l("Feststellung bearbeiten","Edit finding")){
  Picker(l("Raum","Room"),selection:Binding(get:{finding.roomID ?? ""},set:{finding.roomID=$0.isEmpty ? nil:$0})){Text(l("Ohne Raum","No room")).tag("");ForEach(availableRooms,id:\.canonical){value in Text(value["name"].string ?? "").tag(value["id"].string ?? "")}}
  TextField(l("Titel","Title"),text:$finding.title)
  TextField(l("Beschreibung","Description"),text:$finding.description,axis:.vertical).lineLimit(4...10)
  TextField(l("Kategorie","Category"),text:$finding.category)
  Picker(l("Dringlichkeit","Urgency"),selection:$finding.severity){Text(l("Gering","Minor")).tag("minor");Text(l("Normal","Normal")).tag("normal");Text(l("Dringend","Urgent")).tag("urgent")}
  Button(l("Feststellung lokal speichern","Save finding locally")){Task{await saveFinding()}}.disabled(!validFinding)
  if findingEdit != nil{Button(l("Bearbeitung abbrechen","Cancel editing")){guardChange{clearFinding()}}}
 }}
 private func findingSection(_ value:InspectionFinding,_ draft:InspectionDraft)->some View {Section(value.title){
  Text(value.description);Text(value.category+" · "+value.severity).font(.caption)
  if editable{Button(l("Feststellung bearbeiten","Edit finding")){if findingEdit != value.id{guardChange{clearForms();finding=value;findingBase=value;findingEdit=value.id}}};Button(l("Lokale Feststellung entfernen","Remove local finding"),role:.destructive){guardChange{Task{_ = await run{let next=try draft.changed{$0.findings.removeAll{$0.id==value.id};$0.photos.removeAll{$0.findingID==value.id}};try await archive().save(next,photos:[:],expectedRevision:draft.revision)}}}}}
  ForEach(draft.photos.filter{$0.findingID==value.id}){photo in VStack(alignment:.leading){if let bytes=gallery[photo.id],let image=inspectionThumbnail(bytes){Image(uiImage:image).resizable().scaledToFit().frame(maxHeight:180)};Text(photo.name).font(.caption);if editable{Button(l("Lokales Foto entfernen","Remove local photo"),role:.destructive){Task{_ = await run{let next=try draft.changed{$0.photos.removeAll{$0.id==photo.id}};try await archive().save(next,photos:[:],expectedRevision:draft.revision)}}}}}}
  if editable{InspectionPhotoPicker(language:language,remaining:5-draft.photos.filter{$0.findingID==value.id}.count,onPhotos:{if current && self.draft?.id==draft.id{guardPhotos(value.id,$0)}},onError:{if current{error=$0}},onLoading:{loadingImages=$0});if UIImagePickerController.isSourceTypeAvailable(.camera){Button(l("Foto aufnehmen","Take photo")){cameraTarget=value.id;showCamera=true}.disabled(draft.photos.filter{$0.findingID==value.id}.count>=5)}}
  Text(l("Fotos werden sichtbar in JPEG umgewandelt und auf höchstens 1800 Pixel verkleinert; gespeichert und übertragen werden genau diese Bytes.","Photos are converted to JPEG and resized to at most 1800 pixels; exactly those bytes are stored and uploaded.")).font(.caption)
 }}
 private func queuedSection(_ draft:InspectionDraft)->some View {Section(l("Festgeschriebener Ausgang","Sealed outbox")){
  Text(l("Inhalt und Vorgangskennung bleiben gleich. Ein unklarer Ausgang wird nicht automatisch als Erfolg oder Fehlschlag gewertet.","Content and operation identity stay unchanged. An unknown outcome is never automatically treated as success or failure."))
  Button(l("Übertragen / gleichen Versuch wiederholen","Publish / retry same operation")){Task{await publish(draft)}}.disabled(busy || blocked)
  Button(l("Bestätigung und aktuellen Stand prüfen","Check receipt and current record")){Task{await checkOutcome(draft)}}.disabled(busy || blocked)
  if let review{DisclosureGroup(l("Vorher","Before")){InspectionFacts(snapshot:draft.baseline,language:language)};DisclosureGroup(l("Aktuell","Current")){InspectionFacts(snapshot:review,language:language)};Toggle(l("Aktuellen Stand geprüft; unveröffentlichte Ergänzungen weiter bearbeiten","I reviewed the current record and want to continue editing unpublished additions"),isOn:$confirmed);Text(l("Eine fehlende Bestätigung entsperrt nicht. Zuerst wird die alte Kennung ausdrücklich auf dem Server gesperrt; bei bereits erfolgter Übernahme gilt die echte Bestätigung.","A missing receipt does not unlock editing. The old operation is explicitly cancelled on the server first; if already committed, its real receipt is used."));Button(l("Alte Übertragung beenden und neu abgleichen","Cancel old operation and rebase")){Task{await rebase(draft,review)}}.disabled(!confirmed || busy || review["protocol"]["status"] != .string("draft"));Button(l("Unverändert lassen","Keep unchanged")){self.review=nil;confirmed=false}}
 }}
 private var availableRooms:[InspectionJSON]{(draft?.baseline["rooms"].array ?? [])+(draft?.rooms.compactMap{try? InspectionJSON.encoded($0)} ?? [])}
 private var validRoom:Bool{(try? roomCandidate()) != nil}
 private var validFinding:Bool{(try? findingCandidate()) != nil}
 private func roomCandidate()throws->InspectionDraft{guard let draft else{throw InspectionError.invalid};if let id=roomEdit{try inspectionNeed(draft.rooms.contains{$0.id==id});return try draft.changed{next in next.rooms=next.rooms.map{$0.id==id ? InspectionRoom(id:id,name:room.name.trimmed,condition:room.condition,notes:room.notes):$0}}};return try draft.addingRoom(room)}
 private func findingCandidate()throws->InspectionDraft{guard let draft else{throw InspectionError.invalid};if let id=findingEdit{try inspectionNeed(draft.findings.contains{$0.id==id});return try draft.changed{next in next.findings=next.findings.map{$0.id==id ? InspectionFinding(id:id,roomID:finding.roomID,title:finding.title.trimmed,description:finding.description,category:finding.category,severity:finding.severity):$0}}};return try draft.addingFinding(finding)}
 private func stateLabel(_ state:InspectionDraft.State)->String{switch state{case .draft:return l("Lokal gespeichert · nicht übertragen","Saved locally · not published");case .queued:return l("Wartet auf Bestätigung","Awaiting acknowledgement");case .acknowledged:return l("Vom Server bestätigt","Acknowledged by server")}}
 private func guardChange(_ action:@escaping ()->Void){if dirty{nextAction=action;showDiscard=true}else{action()}}
 private func clearRoom(){room=InspectionRoom(id:UUID().uuidString.lowercased(),name:"",condition:"ok",notes:"");roomBase=nil;roomEdit=nil}
 private func clearFinding(){finding=InspectionFinding(id:UUID().uuidString.lowercased(),roomID:nil,title:"",description:"",category:"Sonstiges",severity:"normal");findingBase=nil;findingEdit=nil}
 private func clearForms(){clearRoom();clearFinding();pendingImages=[];photoTarget=nil;review=nil;confirmed=false}
 private func reload()async{guard current else{return};do{let values=try await archive().load();guard current else{return};drafts=values.filter{$0.protocolID==protocolID && $0.organizationID==initialSnapshot["protocol"]["organization_id"].string};if !drafts.contains(where:{$0.id==selectedID}){selectedID=drafts.last?.id ?? ""};blocked=false;await loadGallery()}catch{if current{blocked=true;self.error=error.localizedDescription}}}
 private func loadGallery()async{gallery=[:];guard let draft,current else{return};do{let bytes=try await archive().photos(draftID:draft.id);if current && self.draft?.id==draft.id{gallery=bytes}}catch{if current{blocked=true;self.error=error.localizedDescription}}}
 private func run(_ action:()async throws->Void)async->Bool{guard current,!busy,!blocked else{return false};busy=true;error=nil;defer{busy=false};do{try await action();guard current else{return false};await reload();return !blocked}catch{if current{self.error=error.localizedDescription;if let e=error as? InspectionError,e == .corrupt || e == .future || e == .deleted{blocked=true}};return false}}
 private func newDraft()async{let success=await run{let source=try await session.api.inspectionDetail(id:protocolID,current:{current});try inspectionNeed(source["protocol"]["id"] == .string(protocolID) && source["protocol"]["organization_id"] == initialSnapshot["protocol"]["organization_id"],.identity);let value=try InspectionDraft.create(id:UUID().uuidString.lowercased(),ownerID:ownerID,organizationID:source["protocol"]["organization_id"].string,snapshot:source,at:inspectionStamp());try await archive().save(value,photos:[:],expectedRevision:nil);if current{selectedID=value.id}};if success{clearForms()}}
 private func saveRoom()async{guard let draft else{return};let success=await run{try await archive().save(roomCandidate(),photos:[:],expectedRevision:draft.revision)};if success{clearRoom()}}
 private func saveFinding()async{guard let draft else{return};let success=await run{try await archive().save(findingCandidate(),photos:[:],expectedRevision:draft.revision)};if success{clearFinding()}}
 private func guardPhotos(_ findingID:String,_ images:[DraftImage]){guard current else{return};guardChange{clearForms();pendingImages=images;photoTarget=findingID;Task{await savePhotos()}}}
 private func savePhotos()async{guard let draft,let target=photoTarget,!pendingImages.isEmpty else{return};let images=pendingImages;let success=await run{var next=draft;var data:[String:Data]=[:];for image in images{let photo=try InspectionPhoto(id:UUID().uuidString.lowercased(),findingID:target,name:image.fileName,mime:image.mimeType,data:image.data);next=try next.addingPhoto(photo);data[photo.id]=image.data};try inspectionNeed(current,.identity);try await archive().save(next,photos:data,expectedRevision:draft.revision)};if success{pendingImages=[];photoTarget=nil}}
 private func seal(_ draft:InspectionDraft)async{_ = await run{let next=try draft.sealed(operationID:UUID().uuidString.lowercased(),at:inspectionStamp());try await archive().save(next,photos:[:],expectedRevision:draft.revision)};clearForms()}
 private func accept(_ receipt:InspectionReceipt,_ draft:InspectionDraft)async throws{let next=try draft.acknowledged(receipt);try inspectionNeed(current,.identity);try await archive().save(next,photos:[:],expectedRevision:draft.revision)}
 private func publish(_ draft:InspectionDraft)async{_ = await run{let bytes=try await archive().photos(draftID:draft.id);try inspectionNeed(current,.identity);let receipt=try await session.api.inspectionPublish(draft,photos:bytes,current:{current});try await accept(receipt,draft)}}
 private func checkOutcome(_ draft:InspectionDraft)async{_ = await run{let result=try await session.api.inspectionOutcome(draft,cancel:false,current:{current});if result["exists"] == .bool(true){let receipt=try JSONDecoder().decode(InspectionReceipt.self,from:Data(result["receipt"].canonical.utf8));try await accept(receipt,draft)}else{let snapshot=try await session.api.inspectionDetail(id:protocolID,current:{current});_=try InspectionDraft.normalized(snapshot);if current{review=snapshot;confirmed=false}}}}
 private func rebase(_ draft:InspectionDraft,_ snapshot:InspectionJSON)async{guard confirmed else{return};_ = await run{let result=try await session.api.inspectionOutcome(draft,cancel:true,current:{current});if result["exists"] == .bool(true){let receipt=try JSONDecoder().decode(InspectionReceipt.self,from:Data(result["receipt"].canonical.utf8));try await accept(receipt,draft)}else{try inspectionNeed(current,.identity);let proof=InspectionCancellation(ownerID:ownerID,protocolID:protocolID,operationID:draft.operationID!,payload:draft.batchPayload!,cancelled:result["cancelled"] == .bool(true));try await archive().rebase(draftID:draft.id,expectedRevision:draft.revision,snapshot:snapshot,evidence:proof,confirmed:confirmed)};if current{review=nil;confirmed=false}}}
}
func inspectionStamp()->String{let f=ISO8601DateFormatter();f.formatOptions=[.withInternetDateTime,.withFractionalSeconds];return f.string(from:Date())}

private struct InspectionPhotoPicker:View {
 let language:String,remaining:Int,onPhotos:([DraftImage])->Void,onError:(String)->Void,onLoading:(Bool)->Void
 @State private var selection:[PhotosPickerItem]=[]
 @State private var loading=false
 var body:some View{PhotosPicker(selection:$selection,maxSelectionCount:max(1,remaining),matching:.images){Label(inspectionLabel(language,"Fotos auswählen","Select photos"),systemImage:"photo.on.rectangle")}.disabled(remaining<=0 || loading).onChange(of:selection){_,items in guard !items.isEmpty else{return};loading=true;onLoading(true);Task{do{var images:[DraftImage]=[];for item in items{guard let data=try await item.loadTransferable(type:Data.self)else{throw InspectionError.invalid};images.append(try inspectionJPEG(data:data))};onLoading(false);onPhotos(images)}catch{onLoading(false);onError(error.localizedDescription)};selection=[];loading=false}}}
}
func inspectionThumbnail(_ data:Data)->UIImage?{guard let source=CGImageSourceCreateWithData(data as CFData,nil),let cg=CGImageSourceCreateThumbnailAtIndex(source,0,[kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceThumbnailMaxPixelSize:600,kCGImageSourceCreateThumbnailWithTransform:true] as CFDictionary)else{return nil};return UIImage(cgImage:cg)}
func inspectionJPEG(data:Data)throws->DraftImage{guard let source=CGImageSourceCreateWithData(data as CFData,nil),let cg=CGImageSourceCreateThumbnailAtIndex(source,0,[kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceThumbnailMaxPixelSize:1800,kCGImageSourceCreateThumbnailWithTransform:true] as CFDictionary)else{throw InspectionError.invalid};return try inspectionJPEG(image:UIImage(cgImage:cg))}
func inspectionJPEG(image:UIImage)throws->DraftImage{let scale=min(1,1800/max(image.size.width,image.size.height));let size=CGSize(width:max(1,image.size.width*scale),height:max(1,image.size.height*scale));let format=UIGraphicsImageRendererFormat();format.scale=1;format.opaque=true;let result=UIGraphicsImageRenderer(size:size,format:format).image{context in UIColor.white.setFill();context.fill(CGRect(origin:.zero,size:size));image.draw(in:CGRect(origin:.zero,size:size))};guard let data=result.jpegData(compressionQuality:0.82),data.count<=3*1024*1024 else{throw InspectionError.capacity};return DraftImage(data:data,fileName:"inspection-\(UUID().uuidString.lowercased()).jpg",mimeType:"image/jpeg")}
