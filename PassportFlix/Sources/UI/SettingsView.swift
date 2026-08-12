import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var settingsStore: SettingsStore
    @EnvironmentObject private var library: LibraryStore

    @State private var showClearedAlert = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("IP-adres of hostnaam", text: $settingsStore.settings.host)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    TextField("Share-naam", text: $settingsStore.settings.share)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    TextField("Map met films (optioneel)", text: $settingsStore.settings.rootPath)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                } header: {
                    Text("My Passport Wireless Pro")
                } footer: {
                    Text("Standaard is de WD bereikbaar op 192.168.60.1 met de share \u{201C}Storage\u{201D} zodra je iPad of iPhone met het wifi-netwerk van de WD verbonden is. Laat \u{201C}Map met films\u{201D} leeg om de hele share te scannen, of vul bijv. \u{201C}Films\u{201D} in om sneller te scannen.")
                }

                Section {
                    TextField("Gebruikersnaam (leeg = gast)", text: $settingsStore.settings.username)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    SecureField("Wachtwoord", text: $settingsStore.settings.password)
                } header: {
                    Text("Aanmelding")
                } footer: {
                    Text("Alleen nodig als je op de WD een wachtwoord op de share hebt ingesteld.")
                }

                Section {
                    Button {
                        Task { await library.refresh(settings: settingsStore.settings) }
                    } label: {
                        if library.isBusy {
                            HStack {
                                ProgressView()
                                Text(scanningLabel)
                            }
                        } else {
                            Label("Bibliotheek opnieuw scannen", systemImage: "arrow.clockwise")
                        }
                    }
                    .disabled(library.isBusy)

                    Button(role: .destructive) {
                        Task {
                            await ArtworkCache.shared.clear()
                            showClearedAlert = true
                        }
                    } label: {
                        Label("Afbeeldingscache wissen", systemImage: "trash")
                    }
                } header: {
                    Text("Bibliotheek")
                } footer: {
                    statusFooter
                }
            }
            .navigationTitle("Instellingen")
            .alert("Afbeeldingscache gewist", isPresented: $showClearedAlert) {
                Button("OK", role: .cancel) {}
            }
        }
    }

    private var scanningLabel: String {
        if case .scanning = library.state { return "Scannen…" }
        return "Verbinden…"
    }

    @ViewBuilder
    private var statusFooter: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("\(library.movies.count) films in de bibliotheek.")
            if let lastScan = library.lastScan {
                Text("Laatste scan: \(lastScan.formatted(date: .abbreviated, time: .shortened))")
            }
            if case .failed(let message) = library.state {
                Text(message).foregroundStyle(Theme.accent)
            }
        }
    }
}
