import Foundation

struct User: Codable, Identifiable, Hashable {
    let id: String
    var name: String
    var email: String
    var street: String
    var postalCode: String
    var city: String
    var country: String
    var phone: String
    var emailVerified: Bool
    var planCode: String
    var subscriptionStatus: String
    var subscriptionCurrentPeriodEnd: String?
    var onboardingCompleted: Bool
    var onboardingUseCase: String?

    var planLabel: String {
        switch planCode {
        case "private_pro": return "Privat Pro"
        case "private_free": return "Privat Free"
        case "management_trial": return "Verwaltung · Testphase"
        case "management_starter": return "Verwaltung Starter"
        case "management_pro": return "Verwaltung Pro"
        case "management_business": return "Verwaltung Business"
        default: return planCode
        }
    }
}

struct DefectCase: Codable, Identifiable, Hashable {
    let id: String
    var userId: String?
    var organizationId: String?
    var title: String
    var category: String?
    var description: String?
    var propertyLabel: String?
    var locationLabel: String?
    var discoveredOn: String?
    var recipientName: String?
    var recipientEmail: String?
    var recipientAddress: String?
    var deadlineOn: String?
    var status: String
    var caseContext: String?
    var referenceLabel: String?
    var subjectLabel: String?
    var assignedUserName: String?
    var attachmentCount: Int?
    var submittedByTenant: Bool?
    var archivedAt: String?
    var createdAt: String?
    var updatedAt: String?

    var statusLabel: String {
        switch status {
        case "draft": return "Entwurf"
        case "sent": return "Versendet"
        case "reply": return "Rückmeldung"
        case "received": return "Eingegangen"
        case "reviewing": return "In Prüfung"
        case "commissioned": return "Beauftragt"
        case "scheduled": return "Terminiert"
        case "in_progress": return "In Bearbeitung"
        case "resolved": return "Erledigt"
        default: return status
        }
    }
}

struct CaseEvent: Codable, Identifiable, Hashable {
    let id: String
    var eventType: String?
    var note: String?
    var visibility: String?
    var actorName: String?
    var createdAt: String?
}

struct CaseAttachment: Codable, Identifiable, Hashable {
    let id: String
    var originalName: String
    var mimeType: String?
    var sizeBytes: Int?
    var evidenceType: String?
    var note: String?
    var capturedAt: String?
    var source: String?
    var createdAt: String?

    var isImage: Bool { mimeType?.hasPrefix("image/") == true }
    var isPDF: Bool { mimeType == "application/pdf" }
}

struct CaseMessage: Codable, Identifiable, Hashable {
    let id: String
    var message: String
    var actorName: String?
    var createdAt: String?
}

struct Entitlements: Codable, Hashable {
    let scope: String
    let pro: Bool
    let planCode: String
    let status: String
    let trialEndsAt: String?
    let role: String?
    let provider: String?
    let usage: EntitlementUsage
    let limits: EntitlementLimits
    let features: EntitlementFeatures
}

struct EntitlementUsage: Codable, Hashable {
    var activeCases: Int?
    var members: Int?
    var properties: Int?
    var units: Int?
}

struct EntitlementLimits: Codable, Hashable {
    var maxActiveCases: Int?
    var maxPhotosPerCase: Int?
    var members: Int?
    var properties: Int?
    var units: Int?
}

struct EntitlementFeatures: Codable, Hashable {
    var advancedEvidence: Bool
    var deadlines: Bool
    var tasks: Bool
    var calendar: Bool
    var analytics: Bool
    var archive: Bool
    var inspections: Bool
}

struct ManagementOrganization: Codable, Identifiable, Hashable {
    let id: String
    var name: String
    var planCode: String?
    var role: String?
    var subscriptionStatus: String?
    var trialEndsAt: String?
    var maxMembers: Int?
    var maxProperties: Int?
    var maxUnits: Int?
}

struct ManagementMetrics: Codable, Hashable {
    var properties: Int
    var units: Int
    var contacts: Int
    var open: Int
    var unassigned: Int
    var overdue: Int
}

struct ManagementRecentCase: Codable, Identifiable, Hashable {
    let id: String
    var title: String
    var status: String
    var deadlineOn: String?
    var assignedUserId: String?
    var propertyName: String?
    var unitLabel: String?
    var assignedUserName: String?

    var statusLabel: String {
        switch status {
        case "received": return "Eingegangen"
        case "reviewing": return "In Prüfung"
        case "commissioned": return "Beauftragt"
        case "scheduled": return "Terminiert"
        case "in_progress": return "In Ausführung"
        case "resolved": return "Erledigt"
        case "draft": return "Entwurf"
        case "sent": return "Versendet"
        case "reply": return "Rückmeldung"
        default: return status
        }
    }
}

struct ManagementMember: Codable, Identifiable, Hashable {
    let id: String
    var name: String
    var role: String
    var openCases: Int
}

struct ManagementOverviewResponse: Decodable {
    let organization: ManagementOrganization?
    let metrics: ManagementMetrics?
    let recent: [ManagementRecentCase]?
    let members: [ManagementMember]?
}

struct RegisterResponse: Decodable {
    let user: User
    let accountType: String?
    let organization: ManagementOrganization?
    let verificationMailSent: Bool?
}

struct UserResponse: Decodable { let user: User }
struct CasesResponse: Decodable { let cases: [DefectCase] }

struct CaseResponse: Decodable {
    let caseItem: DefectCase
    enum CodingKeys: String, CodingKey { case caseItem = "case" }
}

struct CaseDetailResponse: Decodable {
    let caseItem: DefectCase
    let events: [CaseEvent]
    let attachments: [CaseAttachment]
    let messages: [CaseMessage]
    let viewerRole: String?
    enum CodingKeys: String, CodingKey {
        case caseItem = "case"
        case events, attachments, messages, viewerRole
    }
}

struct AttachmentsResponse: Decodable { let attachments: [CaseAttachment] }
struct MessageResponse: Decodable { let message: CaseMessage }
struct SimpleResponse: Decodable {
    var ok: Bool?
    var sent: Bool?
    var alreadyVerified: Bool?
    var message: String?
}

struct CreateCaseRequest: Encodable {
    var title: String
    var description: String
    var caseContext: String
    var category: String
    var propertyLabel: String?
    var locationLabel: String?
    var discoveredOn: String?
    var recipientName: String?
    var recipientEmail: String?
    var recipientAddress: String?
    var deadlineOn: String?
    var destinationLinkId: String?
}

struct UpdateCaseRequest: Encodable {
    var title: String?
    var category: String?
    var description: String?
    var propertyLabel: String?
    var locationLabel: String?
    var discoveredOn: String?
    var recipientName: String?
    var recipientEmail: String?
    var recipientAddress: String?
    var deadlineOn: String?
    var status: String?
}

struct UpdateProfileRequest: Encodable {
    var name: String
    var street: String
    var postalCode: String
    var city: String
    var country: String
    var phone: String
}
