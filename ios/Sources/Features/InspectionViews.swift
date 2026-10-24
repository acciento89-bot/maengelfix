import SwiftUI
import PhotosUI
import UIKit
import ImageIO
import Observation

@MainActor @Observable final class InspectionCleanupNotice {static let shared=InspectionCleanupNotice();var message:String?}

func inspectionLabel(_ language:String,_ de:String,_ en:String)->String{language=="de" ? de:en}
struct InspectionSelection:Identifiable {let id:String;let snapshot:InspectionJSON}

struct InspectionsView:View {
 @Environment(AppSession.self) private var session
 let ownerID:String
 @AppStorage("maengelfix.inspection.language") private var language=Locale.current.language.languageCode?.identifier == "de" ? "de":"en"
 @State private var protocols:[InspectionJSON]=[]
 @State private var organizationID:String?
 @State private var busy=false
 @State private var error:String?
 @State private var showCreate=false
 @State private var loaded=false
 private var current:Bool{session.phase == .signedIn && session.user?.id==ownerID}
 private func l(_ de:String,_ en:String)->String{inspectionLabel(language,de,en)}
 var body:some View {
  NavigationStack {
   List {
    Section {Picker(l("Sprache","Language"),selection:$language){Text("Deutsch").tag("de");Text("English").tag("en")}}
    Section {Text(l("Begehungen mit neuen Räumen, Feststellungen und Fotos. Der lokale Ausgang ergänzt ein bestehendes Protokoll erst nach deiner ausdrücklichen Übertragung.","Inspections with new rooms, findings and photos. The local outbox adds to an existing inspection only when you explicitly publish it."))}
    if let error{Section{Text(error).foregroundStyle(.red)}}
    if busy{ProgressView()}
    ForEach(protocols,id:\.canonical){value in
     if let id=value["id"].string {
      NavigationLink {InspectionDetailView(ownerID:ownerID,protocolID:id,language:language)}label:{VStack(alignment:.leading){Text(value["title"].string ?? "").font(.headline);Text(value["status"] == .string("completed") ? l("Abgeschlossen","Completed"):l("Entwurf","Draft")).font(.caption);if let property=value["property_name"].string{Text(property).font(.caption)}}}
     }
    }
    if !busy && protocols.isEmpty{Text(l("Noch keine Begehungen geladen.","No inspections loaded yet."))}
    Button(l("Erneut laden","Reload")){Task{await load()}}.disabled(busy)
   }
   .navigationTitle(l("Begehungen","Inspections"))
   .toolbar{ToolbarItem(placement:.topBarTrailing){Button(l("Neu","New")){showCreate=true}.disabled(busy || !current || !loaded)}}
   .task{await load()}
   .refreshable{await load()}
   .sheet(isPresented:$showCreate,onDismiss:{Task{await load()}}){InspectionCreateView(ownerID:ownerID,organizationID:organizationID,language:language)}
  }
 }
 @MainActor private func load()async{guard current,!busy else{return};busy=true;error=nil;defer{busy=false};do{let value=try await session.api.inspectionList(current:{current});guard current else{return};guard let list=value["protocols"].array else{throw InspectionError.invalid};try inspectionNeed(value["organization"] == .null || value["organization"]["id"].string != nil);protocols=list;organizationID=value["organization"]["id"].string;loaded=true}catch{if current{self.error=error.localizedDescription}}}
}

private struct InspectionCreateView:View {
 @Environment(AppSession.self) private var session
 @Environment(\.dismiss) private var dismiss
 let ownerID:String,organizationID:String?,language:String
 @State private var title=""
 @State private var type="handover"
 @State private var tenant=""
 @State private var email=""
 @State private var notes=""
 @State private var property=""
 @State private var unit=""
 @State private var initialDate:Date?
 @State private var date=Date()
 @State private var properties:[InspectionJSON]=[]
 @State private var units:[InspectionJSON]=[]
 @State private var busy=false
 @State private var error:String?
 @State private var confirmClose=false
 private var current:Bool{session.phase == .signedIn && session.user?.id==ownerID}
 private var valid:Bool{!title.trimmed.isEmpty && title.unicodeScalars.count<=180 && notes.unicodeScalars.count<=3000 && tenant.unicodeScalars.count<=160 && email.unicodeScalars.count<=254 && (organizationID == nil || (!property.isEmpty && !unit.isEmpty))}
 private var dirty:Bool{date != (initialDate ?? date) || !title.isEmpty || type != "handover" || !tenant.isEmpty || !email.isEmpty || !notes.isEmpty || !property.isEmpty || !unit.isEmpty}
 private func l(_ de:String,_ en:String)->String{inspectionLabel(language,de,en)}
 var body:some View {
  NavigationStack{Form{
   Section(l("Neues Online-Protokoll","New online inspection")){
    TextField(l("Titel","Title"),text:$title)
    Picker(l("Art","Type"),selection:$type){Text(l("Übergabe","Handover")).tag("handover");Text(l("Abnahme","Return")).tag("return");Text(l("Begehung","Inspection")).tag("inspection")}
    DatePicker(l("Termin","Date"),selection:$date)
    if organizationID != nil {
     Picker(l("Objekt","Property"),selection:$property){Text(l("Bitte wählen","Choose")).tag("");ForEach(properties,id:\.canonical){p in Text(p["name"].string ?? "").tag(p["id"].string ?? "")}}
     Picker(l("Einheit","Unit"),selection:$unit){Text(l("Bitte wählen","Choose")).tag("");ForEach(units,id:\.canonical){u in Text(u["label"].string ?? "").tag(u["id"].string ?? "")}}
    }
    TextField(l("Beteiligte Person","Participant"),text:$tenant)
    TextField(l("E-Mail (optional)","Email (optional)"),text:$email).textInputAutocapitalization(.never).keyboardType(.emailAddress)
    TextField(l("Allgemeine Notizen","General notes"),text:$notes,axis:.vertical).lineLimit(3...8)
    Text(l("Anlegen benötigt eine Verbindung und den vorhandenen Tarif/Zugriff. Danach können neue Ergänzungen im lokalen Ausgang erfasst werden.","Creation requires connectivity and your existing plan/access. You can then capture new additions in the local outbox." )).font(.caption)
   }.disabled(busy)
   if let error{Text(error).foregroundStyle(.red)}
   Button(l("Protokoll online anlegen","Create inspection online")){Task{await create()}}.disabled(busy || !valid)
   if busy{ProgressView()}
  }.scrollDismissesKeyboard(.interactively).navigationTitle(l("Neue Begehung","New inspection"))
   .toolbar{ToolbarItem(placement:.cancellationAction){Button(l("Schließen","Close")){if dirty{confirmClose=true}else{dismiss()}}.disabled(busy)}}
   .confirmationDialog(l("Nicht gespeicherte Eingaben verwerfen?","Discard unsaved input?"),isPresented:$confirmClose,titleVisibility:.visible){Button(l("Verwerfen","Discard"),role:.destructive){dismiss()};Button(l("Abbrechen","Cancel"),role:.cancel){}}
   .onAppear{if initialDate == nil{initialDate=date}}
   .task{if organizationID != nil{do{let response=try await session.api.inspectionProperties(current:{current});if current{properties=response["properties"].array ?? []}}catch{if current{self.error=error.localizedDescription}}}}
   .task(id:property){unit="";units=[];guard !property.isEmpty else{return};let requested=property;do{let result=try await session.api.inspectionProperty(id:requested,current:{current});if current && property==requested{units=result["units"].array ?? []}}catch{if current && property==requested{self.error=error.localizedDescription}}}
  }.interactiveDismissDisabled(dirty || busy)
 }
 @MainActor private func create()async{guard !busy,current,valid else{return};busy=true;error=nil;defer{busy=false};do{let f=ISO8601DateFormatter();let input:InspectionJSON = .object(["title":.string(title),"protocolType":.string(type),"propertyId":property.isEmpty ? .null:.string(property),"unitId":unit.isEmpty ? .null:.string(unit),"inspectionAt":.string(f.string(from:date)),"tenantName":.string(tenant),"tenantEmail":.string(email),"generalNotes":.string(notes)]);_=try await session.api.inspectionCreate(input,current:{current});if current{dismiss()}}catch{if current{self.error=error.localizedDescription}}}
}

private struct InspectionDetailView:View {
 @Environment(AppSession.self) private var session
 let ownerID:String,protocolID:String,language:String
 @State private var snapshot:InspectionJSON?
 @State private var selected:InspectionSelection?
 @State private var error:String?
 @State private var pdf:URL?
 @State private var busy=false
 private var current:Bool{session.phase == .signedIn && session.user?.id==ownerID}
 private func l(_ de:String,_ en:String)->String{inspectionLabel(language,de,en)}
 var body:some View {
  Form {
   if let snapshot{Section{InspectionFacts(snapshot:snapshot,language:language)}
    Section{Button(l("Lokalen Ausgang öffnen","Open local outbox")){Task{await open()}}.disabled(busy)
     Text(l("Öffnen benötigt aktuellen Online-Zugriff. Ein Ausgang sendet keine Nachrichten, schließt kein Protokoll ab und legt keinen Mangel automatisch an.","Opening requires current online access. An outbox sends no messages, does not complete an inspection and never creates a case automatically.")).font(.caption)
     Button(l("Server-PDF laden","Load server PDF")){Task{await loadPDF()}}.disabled(busy)
     if let pdf{ShareLink(l("Server-PDF teilen","Share server PDF"),item:pdf)}
    }
   }
   if busy{ProgressView()};if let error{Text(error).foregroundStyle(.red)}
   Button(l("Aktuellen Stand laden","Load current record")){Task{await load()}}.disabled(busy)
  }.navigationTitle(l("Protokoll","Inspection")).task{await load()}
   .sheet(item:$selected,onDismiss:{Task{await load()}}){value in InspectionOutboxView(ownerID:ownerID,initialSnapshot:value.snapshot,language:language)}
   .onDisappear{if let pdf{try? FileManager.default.removeItem(at:pdf)}}
 }
 @MainActor private func load()async{guard current,!busy else{return};busy=true;error=nil;defer{busy=false};do{let value=try await session.api.inspectionDetail(id:protocolID,current:{current});_=try InspectionDraft.normalized(value);try inspectionNeed(value["protocol"]["id"] == .string(protocolID),.identity);if current{snapshot=value}}catch{if current{self.error=error.localizedDescription}}}
 @MainActor private func open()async{guard current,!busy else{return};busy=true;error=nil;defer{busy=false};do{let value=try await session.api.inspectionDetail(id:protocolID,current:{current});_=try InspectionDraft.normalized(value);try inspectionNeed(value["protocol"]["id"] == .string(protocolID),.identity);if current{selected=InspectionSelection(id:protocolID,snapshot:value)}}catch{if current{self.error=error.localizedDescription}}}
 @MainActor private func loadPDF()async{guard current,!busy else{return};busy=true;error=nil;defer{busy=false};do{let data=try await session.api.inspectionPDF(id:protocolID,current:{current});guard current else{return};let url=FileManager.default.temporaryDirectory.appendingPathComponent("inspection-\(UUID().uuidString).pdf");try data.write(to:url,options:.atomic);if let pdf{try? FileManager.default.removeItem(at:pdf)};pdf=url}catch{if current{self.error=error.localizedDescription}}}
}

struct InspectionFacts:View {
 let snapshot:InspectionJSON,language:String
 private func l(_ de:String,_ en:String)->String{inspectionLabel(language,de,en)}
 private func field(_ key:String)->String{let names:[String:(String,String)]=["id":("Datensatz-ID","Record ID"),"organization_id":("Organisation","Organization"),"property_id":("Objekt-ID","Property ID"),"unit_id":("Einheiten-ID","Unit ID"),"created_by":("Erstellt durch","Created by"),"protocol_type":("Protokollart","Inspection type"),"status":("Status","Status"),"inspection_at":("Termin","Inspection date"),"tenant_name":("Beteiligte Person","Participant"),"tenant_email":("E-Mail","Email"),"completed_at":("Abgeschlossen am","Completed at"),"created_at":("Erstellt am","Created at"),"updated_at":("Aktualisiert am","Updated at"),"position":("Position","Position"),"category":("Kategorie","Category"),"severity":("Dringlichkeit","Urgency"),"defect_case_id":("Übernommener Mangel","Converted case")];let name=names[key] ?? (key,key);return l(name.0,name.1)}
 private func value(_ json:InspectionJSON)->String{if let text=json.string{let labels:[String:(String,String)]=["draft":("Entwurf","Draft"),"completed":("Abgeschlossen","Completed"),"open":("Offen","Open"),"normal":("Normal","Normal"),"minor":("Gering","Minor"),"urgent":("Dringend","Urgent"),"handover":("Übergabe","Handover"),"return":("Abnahme","Return"),"inspection":("Begehung","Inspection")];if let pair=labels[text]{return l(pair.0,pair.1)};return text};if let number=json.integer{return String(number)};return l("Nicht hinterlegt","Not recorded")}
 var body:some View {VStack(alignment:.leading,spacing:12){
  Text(snapshot["protocol"]["title"].string ?? "").font(.headline)
  ForEach(["protocol_type","status","inspection_at","tenant_name","tenant_email","property_id","unit_id","organization_id","created_by","created_at","updated_at","completed_at"],id:\.self){key in if snapshot["protocol"][key] != .null{LabeledContent(field(key),value:value(snapshot["protocol"][key]))}}
  if let notes=snapshot["protocol"]["general_notes"].string,!notes.isEmpty{Text(l("Allgemeine Notizen","General notes")).bold();Text(notes)}
  ForEach(snapshot["rooms"].array ?? [],id:\.canonical){room in VStack(alignment:.leading){Text(room["name"].string ?? "").bold();Text(inspectionCondition(room["condition"].string ?? "ok",language));if let notes=room["notes"].string{Text(notes)};ForEach(["id","position","created_at"],id:\.self){key in if room[key] != .null{LabeledContent(field(key),value:value(room[key])).font(.caption)}}}}
  ForEach(snapshot["findings"].array ?? [],id:\.canonical){finding in VStack(alignment:.leading){Text(finding["title"].string ?? "").bold();Text(finding["description"].string ?? "");if let roomID=finding["room_id"].string{Text((snapshot["rooms"].array ?? []).first{$0["id"] == .string(roomID)}?["name"].string ?? roomID)};ForEach(["id","category","severity","status","created_by","created_at","updated_at","defect_case_id"],id:\.self){key in if finding[key] != .null{LabeledContent(field(key),value:value(finding[key])).font(.caption)}};Text("\(finding["attachment_count"].integer ?? 0) "+l("Fotos","photos")).font(.caption)}}
 }.frame(maxWidth:.infinity,alignment:.leading)}
}

func inspectionCondition(_ value:String,_ language:String)->String{switch value{case "notice":return inspectionLabel(language,"Hinweis","Note");case "defect":return inspectionLabel(language,"Mangel","Defect");default:return inspectionLabel(language,"In Ordnung","OK")}}
