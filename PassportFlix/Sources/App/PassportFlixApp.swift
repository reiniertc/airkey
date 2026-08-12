import SwiftUI

@main
struct PassportFlixApp: App {
    @StateObject private var library = LibraryStore()
    @StateObject private var settingsStore = SettingsStore.shared
    @StateObject private var progressStore = ProgressStore.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(library)
                .environmentObject(settingsStore)
                .environmentObject(progressStore)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var library: LibraryStore
    @EnvironmentObject private var settingsStore: SettingsStore

    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("Home", systemImage: "house.fill") }

            AllMoviesView()
                .tabItem { Label("Films", systemImage: "square.grid.3x3.fill") }

            SettingsView()
                .tabItem { Label("Instellingen", systemImage: "gearshape.fill") }
        }
        .task {
            if library.movies.isEmpty {
                await library.refresh(settings: settingsStore.settings)
            } else {
                await library.ensureConnection(settings: settingsStore.settings)
            }
        }
    }
}

enum Theme {
    static let accent = Color(red: 0.9, green: 0.11, blue: 0.14) // Netflix-rood
    static let background = Color.black
    static let card = Color(white: 0.12)
}
