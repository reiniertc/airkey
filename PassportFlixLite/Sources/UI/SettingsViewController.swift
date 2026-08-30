import UIKit

/// Instellingenscherm: verbindingsgegevens van de WD plus bibliotheekacties.
final class SettingsViewController: UITableViewController {

    private let hostField = UITextField()
    private let shareField = UITextField()
    private let rootField = UITextField()
    private let usernameField = UITextField()
    private let passwordField = UITextField()

    init() {
        super.init(style: .grouped)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Instellingen"
        tableView.backgroundColor = Theme.background
        tableView.separatorColor = UIColor(white: 0.25, alpha: 1)
        tableView.keyboardDismissMode = .onDrag

        let settings = SettingsStore.shared.settings
        configure(hostField, placeholder: "IP-adres of hostnaam", value: settings.host, keyboard: .URL)
        configure(shareField, placeholder: "Share-naam", value: settings.share)
        configure(rootField, placeholder: "Map met films (optioneel)", value: settings.rootPath)
        configure(usernameField, placeholder: "Gebruikersnaam (leeg = gast)", value: settings.username)
        configure(passwordField, placeholder: "Wachtwoord", value: settings.password)
        passwordField.isSecureTextEntry = true

        NotificationCenter.default.addObserver(self, selector: #selector(libraryChanged),
                                               name: .libraryDidChange, object: nil)
    }

    private func configure(_ field: UITextField, placeholder: String, value: String,
                           keyboard: UIKeyboardType = .default) {
        field.placeholder = placeholder
        field.text = value
        field.keyboardType = keyboard
        field.autocorrectionType = .no
        field.autocapitalizationType = .none
        field.textColor = .white
        field.keyboardAppearance = .dark
        field.attributedPlaceholder = NSAttributedString(
            string: placeholder, attributes: [.foregroundColor: Theme.secondaryText])
        field.addTarget(self, action: #selector(fieldChanged), for: .editingChanged)
    }

    @objc private func fieldChanged() {
        var settings = SettingsStore.shared.settings
        settings.host = hostField.text ?? ""
        settings.share = shareField.text ?? ""
        settings.rootPath = rootField.text ?? ""
        settings.username = usernameField.text ?? ""
        settings.password = passwordField.text ?? ""
        SettingsStore.shared.settings = settings
    }

    @objc private func libraryChanged() {
        tableView.reloadSections(IndexSet(integer: 2), with: .none)
    }

    // MARK: - Tabelstructuur

    override func numberOfSections(in tableView: UITableView) -> Int { 3 }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        switch section {
        case 0: return 3   // host, share, map
        case 1: return 2   // gebruikersnaam, wachtwoord
        default: return 2  // scannen, cache wissen
        }
    }

    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        switch section {
        case 0: return "My Passport Wireless Pro"
        case 1: return "Aanmelding"
        default: return "Bibliotheek"
        }
    }

    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        switch section {
        case 0:
            return "Standaard is de WD bereikbaar op 192.168.60.1 met de share \u{201C}Storage\u{201D} zodra de iPad met het wifi-netwerk van de WD verbonden is."
        case 1:
            return "Alleen nodig als je op de WD een wachtwoord op de share hebt ingesteld."
        default:
            var lines = ["\(LibraryStore.shared.movies.count) films in de bibliotheek."]
            if let lastScan = LibraryStore.shared.lastScan {
                let formatter = DateFormatter()
                formatter.dateStyle = .medium
                formatter.timeStyle = .short
                lines.append("Laatste scan: \(formatter.string(from: lastScan))")
            }
            if case .failed(let message) = LibraryStore.shared.state {
                lines.append(message)
            }
            return lines.joined(separator: "\n")
        }
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = UITableViewCell(style: .default, reuseIdentifier: nil)
        cell.backgroundColor = Theme.card
        cell.selectionStyle = .none

        switch (indexPath.section, indexPath.row) {
        case (0, 0): embed(hostField, in: cell)
        case (0, 1): embed(shareField, in: cell)
        case (0, 2): embed(rootField, in: cell)
        case (1, 0): embed(usernameField, in: cell)
        case (1, 1): embed(passwordField, in: cell)
        case (2, 0):
            cell.textLabel?.text = LibraryStore.shared.isBusy ? "Bezig met scannen…" : "Bibliotheek opnieuw scannen"
            cell.textLabel?.textColor = LibraryStore.shared.isBusy ? Theme.secondaryText : .white
            cell.selectionStyle = LibraryStore.shared.isBusy ? .none : .default
        default:
            cell.textLabel?.text = "Afbeeldingscache wissen"
            cell.textLabel?.textColor = Theme.accent
            cell.selectionStyle = .default
        }
        return cell
    }

    private func embed(_ field: UITextField, in cell: UITableViewCell) {
        field.translatesAutoresizingMaskIntoConstraints = false
        cell.contentView.addSubview(field)
        NSLayoutConstraint.activate([
            field.leadingAnchor.constraint(equalTo: cell.contentView.layoutMarginsGuide.leadingAnchor),
            field.trailingAnchor.constraint(equalTo: cell.contentView.layoutMarginsGuide.trailingAnchor),
            field.topAnchor.constraint(equalTo: cell.contentView.topAnchor),
            field.bottomAnchor.constraint(equalTo: cell.contentView.bottomAnchor),
            field.heightAnchor.constraint(greaterThanOrEqualToConstant: 44)
        ])
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard indexPath.section == 2 else { return }
        if indexPath.row == 0 {
            guard !LibraryStore.shared.isBusy else { return }
            LibraryStore.shared.refresh()
            tableView.reloadSections(IndexSet(integer: 2), with: .none)
        } else {
            ArtworkCache.shared.clear()
            let alert = UIAlertController(title: "Afbeeldingscache gewist", message: nil, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            present(alert, animated: true)
        }
    }
}
