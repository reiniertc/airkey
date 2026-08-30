import UIKit

/// Doorzoekbaar posterraster met alle films — het hoofdscherm van de Lite-app.
final class LibraryViewController: UICollectionViewController, UISearchResultsUpdating {

    private enum SortOption: Int, CaseIterable {
        case title, year, rating, added

        var label: String {
            switch self {
            case .title: return "Titel"
            case .year: return "Jaar"
            case .rating: return "Waardering"
            case .added: return "Onlangs toegevoegd"
            }
        }
    }

    private var displayedMovies: [Movie] = []
    private var searchText = ""
    private var sortOption: SortOption = .title

    private let statusLabel = UILabel()
    private let statusButton = UIButton(type: .system)
    private let spinner = UIActivityIndicatorView(style: .whiteLarge)
    private let refreshControl = UIRefreshControl()

    init() {
        let layout = UICollectionViewFlowLayout()
        layout.minimumInteritemSpacing = 10
        layout.minimumLineSpacing = 16
        layout.sectionInset = UIEdgeInsets(top: 12, left: 12, bottom: 12, right: 12)
        super.init(collectionViewLayout: layout)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "PASSPORTFLIX"
        collectionView.backgroundColor = Theme.background
        collectionView.register(PosterCell.self, forCellWithReuseIdentifier: PosterCell.reuseID)
        collectionView.contentInsetAdjustmentBehavior = .always

        refreshControl.tintColor = .white
        refreshControl.addTarget(self, action: #selector(refreshPulled), for: .valueChanged)
        collectionView.refreshControl = refreshControl

        let search = UISearchController(searchResultsController: nil)
        search.searchResultsUpdater = self
        search.obscuresBackgroundDuringPresentation = false
        search.searchBar.placeholder = "Zoek op titel of acteur"
        search.searchBar.keyboardAppearance = .dark
        navigationItem.searchController = search
        navigationItem.hidesSearchBarWhenScrolling = true
        definesPresentationContext = true

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Sorteer", style: .plain, target: self, action: #selector(showSortOptions))

        setUpStatusViews()

        NotificationCenter.default.addObserver(self, selector: #selector(libraryChanged),
                                               name: .libraryDidChange, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(progressChanged),
                                               name: .progressDidChange, object: nil)
        reloadData()
    }

    private func setUpStatusViews() {
        statusLabel.textColor = Theme.secondaryText
        statusLabel.font = UIFont.systemFont(ofSize: 15)
        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center

        statusButton.setTitle("Bibliotheek scannen", for: .normal)
        statusButton.titleLabel?.font = UIFont.systemFont(ofSize: 16, weight: .semibold)
        statusButton.addTarget(self, action: #selector(scanTapped), for: .touchUpInside)

        spinner.hidesWhenStopped = true

        let stack = UIStackView(arrangedSubviews: [spinner, statusLabel, statusButton])
        stack.axis = .vertical
        stack.spacing = 14
        stack.alignment = .center
        stack.translatesAutoresizingMaskIntoConstraints = false

        let container = UIView()
        container.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: container.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: container.centerYAnchor, constant: -40),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: container.leadingAnchor, constant: 32),
            stack.trailingAnchor.constraint(lessThanOrEqualTo: container.trailingAnchor, constant: -32)
        ])
        collectionView.backgroundView = container
    }

    // MARK: - Data

    @objc private func libraryChanged() {
        reloadData()
    }

    @objc private func progressChanged() {
        collectionView.reloadData()
    }

    private func reloadData() {
        var movies = LibraryStore.shared.movies
        if !searchText.isEmpty {
            movies = movies.filter {
                $0.title.localizedCaseInsensitiveContains(searchText)
                    || ($0.originalTitle?.localizedCaseInsensitiveContains(searchText) ?? false)
                    || $0.actors.contains { $0.name.localizedCaseInsensitiveContains(searchText) }
            }
        }
        switch sortOption {
        case .title:
            movies.sort { ($0.sortTitle ?? $0.title).localizedCaseInsensitiveCompare($1.sortTitle ?? $1.title) == .orderedAscending }
        case .year:
            movies.sort { ($0.year ?? 0) > ($1.year ?? 0) }
        case .rating:
            movies.sort { ($0.rating ?? 0) > ($1.rating ?? 0) }
        case .added:
            movies.sort { ($0.addedDate ?? .distantPast) > ($1.addedDate ?? .distantPast) }
        }
        displayedMovies = movies
        collectionView.reloadData()
        updateStatusViews()
    }

    private func updateStatusViews() {
        let state = LibraryStore.shared.state
        if !LibraryStore.shared.isBusy {
            refreshControl.endRefreshing()
        }

        guard displayedMovies.isEmpty else {
            collectionView.backgroundView?.isHidden = true
            spinner.stopAnimating()
            return
        }
        collectionView.backgroundView?.isHidden = false

        switch state {
        case .connecting:
            spinner.startAnimating()
            statusLabel.text = "Verbinden met de My Passport Wireless Pro…"
            statusButton.isHidden = true
        case .scanning(let path):
            spinner.startAnimating()
            statusLabel.text = "Bibliotheek scannen…\n\(path)"
            statusButton.isHidden = true
        case .failed(let message):
            spinner.stopAnimating()
            statusLabel.text = message
            statusButton.setTitle("Opnieuw proberen", for: .normal)
            statusButton.isHidden = false
        default:
            spinner.stopAnimating()
            statusLabel.text = searchText.isEmpty
                ? "Nog geen films gevonden. Verbind de iPad met het wifi-netwerk van de WD en scan de bibliotheek."
                : "Geen films gevonden voor \u{201C}\(searchText)\u{201D}."
            statusButton.setTitle("Bibliotheek scannen", for: .normal)
            statusButton.isHidden = !searchText.isEmpty
        }
    }

    // MARK: - Acties

    @objc private func scanTapped() {
        LibraryStore.shared.refresh()
    }

    @objc private func refreshPulled() {
        LibraryStore.shared.refresh()
    }

    @objc private func showSortOptions() {
        let sheet = UIAlertController(title: "Sorteren op", message: nil, preferredStyle: .actionSheet)
        for option in SortOption.allCases {
            let check = option == sortOption ? " ✓" : ""
            sheet.addAction(UIAlertAction(title: option.label + check, style: .default) { [weak self] _ in
                self?.sortOption = option
                self?.reloadData()
            })
        }
        sheet.addAction(UIAlertAction(title: "Annuleer", style: .cancel))
        sheet.popoverPresentationController?.barButtonItem = navigationItem.rightBarButtonItem
        present(sheet, animated: true)
    }

    // MARK: - UISearchResultsUpdating

    func updateSearchResults(for searchController: UISearchController) {
        searchText = searchController.searchBar.text ?? ""
        reloadData()
    }

    // MARK: - UICollectionView

    override func collectionView(_ collectionView: UICollectionView, numberOfItemsInSection section: Int) -> Int {
        displayedMovies.count
    }

    override func collectionView(_ collectionView: UICollectionView,
                                 cellForItemAt indexPath: IndexPath) -> UICollectionViewCell {
        let cell = collectionView.dequeueReusableCell(withReuseIdentifier: PosterCell.reuseID,
                                                      for: indexPath) as! PosterCell
        cell.configure(with: displayedMovies[indexPath.item])
        return cell
    }

    override func collectionView(_ collectionView: UICollectionView, didSelectItemAt indexPath: IndexPath) {
        let detail = DetailViewController(movie: displayedMovies[indexPath.item])
        navigationController?.pushViewController(detail, animated: true)
    }
}

extension LibraryViewController: UICollectionViewDelegateFlowLayout {
    func collectionView(_ collectionView: UICollectionView, layout collectionViewLayout: UICollectionViewLayout,
                        sizeForItemAt indexPath: IndexPath) -> CGSize {
        let available = collectionView.bounds.width - 24
        let columns = max(3, Int(available / 130))
        let width = (available - CGFloat(columns - 1) * 10) / CGFloat(columns)
        return CGSize(width: floor(width), height: floor(width * 1.5) + 20)
    }
}

/// Posterkaart met titelregel eronder, voortgangsbalkje en terugval op een
/// titelkaart wanneer er geen poster bij de film gevonden is.
final class PosterCell: UICollectionViewCell {
    static let reuseID = "PosterCell"

    private let imageView = UIImageView()
    private let fallbackLabel = UILabel()
    private let captionLabel = UILabel()
    private let progressTrack = UIView()
    private let progressFill = UIView()
    private var currentPath: String?
    private var progressWidthConstraint: NSLayoutConstraint?

    override init(frame: CGRect) {
        super.init(frame: frame)

        let posterContainer = UIView()
        posterContainer.backgroundColor = Theme.card
        posterContainer.layer.cornerRadius = 8
        posterContainer.clipsToBounds = true
        posterContainer.translatesAutoresizingMaskIntoConstraints = false
        contentView.addSubview(posterContainer)

        imageView.contentMode = .scaleAspectFill
        imageView.translatesAutoresizingMaskIntoConstraints = false
        posterContainer.addSubview(imageView)

        fallbackLabel.font = UIFont.systemFont(ofSize: 12, weight: .semibold)
        fallbackLabel.textColor = .white
        fallbackLabel.numberOfLines = 4
        fallbackLabel.textAlignment = .center
        fallbackLabel.translatesAutoresizingMaskIntoConstraints = false
        posterContainer.addSubview(fallbackLabel)

        progressTrack.backgroundColor = UIColor(white: 1, alpha: 0.3)
        progressTrack.translatesAutoresizingMaskIntoConstraints = false
        posterContainer.addSubview(progressTrack)

        progressFill.backgroundColor = Theme.accent
        progressFill.translatesAutoresizingMaskIntoConstraints = false
        progressTrack.addSubview(progressFill)

        captionLabel.font = UIFont.systemFont(ofSize: 11)
        captionLabel.textColor = Theme.secondaryText
        captionLabel.textAlignment = .center
        captionLabel.translatesAutoresizingMaskIntoConstraints = false
        contentView.addSubview(captionLabel)

        NSLayoutConstraint.activate([
            posterContainer.topAnchor.constraint(equalTo: contentView.topAnchor),
            posterContainer.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            posterContainer.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            posterContainer.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -20),

            imageView.topAnchor.constraint(equalTo: posterContainer.topAnchor),
            imageView.leadingAnchor.constraint(equalTo: posterContainer.leadingAnchor),
            imageView.trailingAnchor.constraint(equalTo: posterContainer.trailingAnchor),
            imageView.bottomAnchor.constraint(equalTo: posterContainer.bottomAnchor),

            fallbackLabel.centerYAnchor.constraint(equalTo: posterContainer.centerYAnchor),
            fallbackLabel.leadingAnchor.constraint(equalTo: posterContainer.leadingAnchor, constant: 6),
            fallbackLabel.trailingAnchor.constraint(equalTo: posterContainer.trailingAnchor, constant: -6),

            progressTrack.leadingAnchor.constraint(equalTo: posterContainer.leadingAnchor),
            progressTrack.trailingAnchor.constraint(equalTo: posterContainer.trailingAnchor),
            progressTrack.bottomAnchor.constraint(equalTo: posterContainer.bottomAnchor),
            progressTrack.heightAnchor.constraint(equalToConstant: 4),

            progressFill.leadingAnchor.constraint(equalTo: progressTrack.leadingAnchor),
            progressFill.topAnchor.constraint(equalTo: progressTrack.topAnchor),
            progressFill.bottomAnchor.constraint(equalTo: progressTrack.bottomAnchor),

            captionLabel.topAnchor.constraint(equalTo: posterContainer.bottomAnchor, constant: 4),
            captionLabel.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            captionLabel.trailingAnchor.constraint(equalTo: contentView.trailingAnchor)
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    func configure(with movie: Movie) {
        captionLabel.text = movie.title
        fallbackLabel.text = movie.displayYear.isEmpty ? movie.title : "\(movie.title)\n\(movie.displayYear)"
        imageView.image = nil
        fallbackLabel.isHidden = false

        if let fraction = ProgressStore.shared.fraction(for: movie) {
            progressTrack.isHidden = false
            progressWidthConstraint?.isActive = false
            progressWidthConstraint = progressFill.widthAnchor.constraint(
                equalTo: progressTrack.widthAnchor, multiplier: CGFloat(min(max(fraction, 0), 1)))
            progressWidthConstraint?.isActive = true
        } else {
            progressTrack.isHidden = true
        }

        currentPath = movie.posterPath
        guard let posterPath = movie.posterPath else { return }
        ArtworkCache.shared.image(forSMBPath: posterPath, maxPixelSize: 500) { [weak self] image in
            guard let self, self.currentPath == posterPath, let image else { return }
            self.imageView.image = image
            self.fallbackLabel.isHidden = true
        }
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        imageView.image = nil
        currentPath = nil
    }
}
