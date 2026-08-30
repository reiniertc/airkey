import UIKit

enum Theme {
    static let accent = UIColor(red: 0.9, green: 0.11, blue: 0.14, alpha: 1) // Netflix-rood
    static let background = UIColor.black
    static let card = UIColor(white: 0.12, alpha: 1)
    static let secondaryText = UIColor(white: 0.62, alpha: 1)
}

@UIApplicationMain
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        styleAppearance()

        let libraryNav = UINavigationController(rootViewController: LibraryViewController())
        libraryNav.tabBarItem = UITabBarItem(title: "Films", image: Icons.film(), tag: 0)

        let settingsNav = UINavigationController(rootViewController: SettingsViewController())
        settingsNav.tabBarItem = UITabBarItem(title: "Instellingen", image: Icons.sliders(), tag: 1)

        let tabs = UITabBarController()
        tabs.viewControllers = [libraryNav, settingsNav]

        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = tabs
        window.tintColor = Theme.accent
        window.backgroundColor = Theme.background
        window.makeKeyAndVisible()
        self.window = window

        // Cache tonen kan meteen; op de achtergrond alvast verbinden of scannen.
        if LibraryStore.shared.movies.isEmpty {
            LibraryStore.shared.refresh()
        } else {
            LibraryStore.shared.ensureConnection()
        }
        return true
    }

    private func styleAppearance() {
        UINavigationBar.appearance().barStyle = .black
        UINavigationBar.appearance().isTranslucent = false
        UINavigationBar.appearance().barTintColor = Theme.background
        UINavigationBar.appearance().tintColor = .white
        UINavigationBar.appearance().titleTextAttributes = [
            .foregroundColor: Theme.accent,
            .font: UIFont.systemFont(ofSize: 17, weight: .black)
        ]
        UITabBar.appearance().barStyle = .black
        UITabBar.appearance().isTranslucent = false
        UITabBar.appearance().barTintColor = Theme.background
        UITabBar.appearance().tintColor = .white
        UITabBar.appearance().unselectedItemTintColor = Theme.secondaryText
    }
}

/// iOS 12 kent geen SF Symbols; deze iconen worden programmatisch getekend.
enum Icons {
    static func film() -> UIImage {
        render { context in
            let frame = CGRect(x: 2, y: 4, width: 21, height: 17)
            let path = UIBezierPath(roundedRect: frame, cornerRadius: 3)
            path.lineWidth = 1.8
            path.stroke()
            for column in [CGFloat(5.5), CGFloat(19.5)] {
                for row in 0..<3 {
                    let dot = UIBezierPath(ovalIn: CGRect(x: column - 1.1, y: 7 + CGFloat(row) * 4.5,
                                                          width: 2.2, height: 2.2))
                    dot.fill()
                }
            }
            context.stroke(CGRect(x: 9, y: 6.5, width: 7, height: 12))
        }
    }

    static func sliders() -> UIImage {
        render { context in
            for (index, knobX) in [CGFloat(8), CGFloat(17), CGFloat(11)].enumerated() {
                let y = 6 + CGFloat(index) * 6.5
                context.setLineWidth(1.8)
                context.move(to: CGPoint(x: 3, y: y))
                context.addLine(to: CGPoint(x: 22, y: y))
                context.strokePath()
                let knob = UIBezierPath(ovalIn: CGRect(x: knobX - 2.4, y: y - 2.4, width: 4.8, height: 4.8))
                UIColor.black.setFill()
                knob.fill()
                knob.lineWidth = 1.8
                knob.stroke()
            }
        }
    }

    private static func render(_ draw: (CGContext) -> Void) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 25, height: 25))
        let image = renderer.image { rendererContext in
            UIColor.white.setStroke()
            UIColor.white.setFill()
            draw(rendererContext.cgContext)
        }
        return image.withRenderingMode(.alwaysTemplate)
    }
}
