import SwiftUI

extension Color {
    static let mfPrimary = Color(red: 36 / 255, green: 87 / 255, blue: 214 / 255)
    static let mfPrimaryStrong = Color(red: 23 / 255, green: 63 / 255, blue: 168 / 255)
    static let mfAccent = Color(red: 229 / 255, green: 163 / 255, blue: 27 / 255)
    static let mfInk = Color(red: 24 / 255, green: 33 / 255, blue: 43 / 255)
    static let mfBackground = Color(uiColor: UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(red: 16 / 255, green: 21 / 255, blue: 27 / 255, alpha: 1)
            : UIColor(red: 243 / 255, green: 245 / 255, blue: 247 / 255, alpha: 1)
    })
}

struct MFLogo: View {
    var compact = false

    var body: some View {
        HStack(spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: compact ? 8 : 10)
                    .fill(Color.mfInk)
                Image(systemName: "doc.badge.checkmark")
                    .font(.system(size: compact ? 18 : 23, weight: .semibold))
                    .foregroundStyle(Color.white, Color.mfAccent)
            }
            .frame(width: compact ? 38 : 46, height: compact ? 38 : 46)

            VStack(alignment: .leading, spacing: 2) {
                Text("MängelFix")
                    .font(compact ? .headline : .title3.bold())
                if !compact {
                    Text("DOKUMENTIEREN · ORGANISIEREN · NACHWEISEN")
                        .font(.system(size: 8, weight: .bold))
                        .tracking(0.7)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct MFCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(.quaternary, lineWidth: 1)
            }
    }
}
