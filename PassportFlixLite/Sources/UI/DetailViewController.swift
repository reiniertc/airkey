import UIKit

/// Detailpagina met fanart, poster, metadata en afspeelknop.
final class DetailViewController: UIViewController {
    private let movie: Movie

    private let fanartView = UIImageView()
    private let posterView = UIImageView()
    private let playButton = UIButton(type: .system)
    private let restartButton = UIButton(type: .system)

    init(movie: Movie) {
        self.movie = movie
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Theme.background
        navigationItem.title = ""

        let scrollView = UIScrollView()
        scrollView.alwaysBounceVertical = true
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(scrollView)

        let content = UIStackView()
        content.axis = .vertical
        content.spacing = 14
        content.isLayoutMarginsRelativeArrangement = true
        content.layoutMargins = UIEdgeInsets(top: 0, left: 16, bottom: 32, right: 16)
        content.translatesAutoresizingMaskIntoConstraints = false
        scrollView.addSubview(content)

        NSLayoutConstraint.activate([
            scrollView.topAnchor.constraint(equalTo: view.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            content.topAnchor.constraint(equalTo: scrollView.topAnchor),
            content.leadingAnchor.constraint(equalTo: scrollView.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: scrollView.trailingAnchor),
            content.bottomAnchor.constraint(equalTo: scrollView.bottomAnchor),
            content.widthAnchor.constraint(equalTo: view.widthAnchor)
        ])

        buildHeader(in: content)
        buildBody(in: content)
        loadArtwork()
        updatePlayButtons()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        updatePlayButtons()
    }

    // MARK: - Opbouw

    private func buildHeader(in content: UIStackView) {
        let header = UIView()
        header.translatesAutoresizingMaskIntoConstraints = false

        fanartView.contentMode = .scaleAspectFill
        fanartView.clipsToBounds = true
        fanartView.backgroundColor = Theme.card
        fanartView.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(fanartView)

        let gradient = GradientView()
        gradient.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(gradient)

        posterView.contentMode = .scaleAspectFill
        posterView.clipsToBounds = true
        posterView.backgroundColor = Theme.card
        posterView.layer.cornerRadius = 8
        posterView.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(posterView)

        let titleLabel = UILabel()
        titleLabel.text = movie.title
        titleLabel.font = UIFont.systemFont(ofSize: 26, weight: .black)
        titleLabel.textColor = .white
        titleLabel.numberOfLines = 3

        let metaLabel = UILabel()
        var parts: [String] = []
        if !movie.displayYear.isEmpty { parts.append(movie.displayYear) }
        if let runtime = movie.displayRuntime { parts.append(runtime) }
        if let mpaa = movie.mpaa, !mpaa.isEmpty { parts.append(mpaa) }
        if let rating = movie.rating { parts.append(String(format: "★ %.1f", rating)) }
        metaLabel.text = parts.joined(separator: "   ")
        metaLabel.font = UIFont.systemFont(ofSize: 13, weight: .semibold)
        metaLabel.textColor = .white

        let genresLabel = UILabel()
        genresLabel.text = movie.genres.joined(separator: " • ")
        genresLabel.font = UIFont.systemFont(ofSize: 12)
        genresLabel.textColor = Theme.secondaryText
        genresLabel.numberOfLines = 2

        let titleStack = UIStackView(arrangedSubviews: [titleLabel, metaLabel, genresLabel])
        titleStack.axis = .vertical
        titleStack.spacing = 5
        titleStack.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(titleStack)

        NSLayoutConstraint.activate([
            header.heightAnchor.constraint(equalToConstant: 250),

            fanartView.topAnchor.constraint(equalTo: header.topAnchor),
            fanartView.leadingAnchor.constraint(equalTo: header.leadingAnchor),
            fanartView.trailingAnchor.constraint(equalTo: header.trailingAnchor),
            fanartView.heightAnchor.constraint(equalToConstant: 190),

            gradient.topAnchor.constraint(equalTo: fanartView.topAnchor),
            gradient.leadingAnchor.constraint(equalTo: fanartView.leadingAnchor),
            gradient.trailingAnchor.constraint(equalTo: fanartView.trailingAnchor),
            gradient.bottomAnchor.constraint(equalTo: fanartView.bottomAnchor),

            posterView.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 16),
            posterView.bottomAnchor.constraint(equalTo: header.bottomAnchor),
            posterView.widthAnchor.constraint(equalToConstant: 104),
            posterView.heightAnchor.constraint(equalToConstant: 156),

            titleStack.leadingAnchor.constraint(equalTo: posterView.trailingAnchor, constant: 14),
            titleStack.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -16),
            titleStack.bottomAnchor.constraint(equalTo: header.bottomAnchor, constant: -4)
        ])

        content.addArrangedSubview(header)
    }

    private func buildBody(in content: UIStackView) {
        playButton.setTitle("▶  Afspelen", for: .normal)
        playButton.setTitleColor(.black, for: .normal)
        playButton.titleLabel?.font = UIFont.systemFont(ofSize: 17, weight: .bold)
        playButton.backgroundColor = .white
        playButton.layer.cornerRadius = 8
        playButton.heightAnchor.constraint(equalToConstant: 46).isActive = true
        playButton.addTarget(self, action: #selector(playTapped), for: .touchUpInside)
        content.addArrangedSubview(playButton)

        restartButton.setTitle("Opnieuw beginnen", for: .normal)
        restartButton.setTitleColor(Theme.secondaryText, for: .normal)
        restartButton.titleLabel?.font = UIFont.systemFont(ofSize: 13)
        restartButton.addTarget(self, action: #selector(restartTapped), for: .touchUpInside)
        content.addArrangedSubview(restartButton)

        if !movie.subtitles.isEmpty {
            addCaption(to: content,
                       text: "Ondertiteling: " + movie.subtitles.map(\.label).joined(separator: ", "))
        }

        if let tagline = movie.tagline, !tagline.isEmpty {
            let label = UILabel()
            label.text = "\u{201C}\(tagline)\u{201D}"
            label.font = UIFont.italicSystemFont(ofSize: 14)
            label.textColor = Theme.secondaryText
            label.numberOfLines = 0
            content.addArrangedSubview(label)
        }

        if let plot = movie.plot, !plot.isEmpty {
            let label = UILabel()
            label.text = plot
            label.font = UIFont.systemFont(ofSize: 15)
            label.textColor = UIColor(white: 0.9, alpha: 1)
            label.numberOfLines = 0
            content.addArrangedSubview(label)
        }

        if !movie.directors.isEmpty {
            addCaption(to: content, text: "Regie: " + movie.directors.joined(separator: ", "))
        }
        if !movie.actors.isEmpty {
            let names = movie.actors.prefix(10).map { actor -> String in
                if let role = actor.role, !role.isEmpty { return "\(actor.name) (\(role))" }
                return actor.name
            }
            addCaption(to: content, text: "Cast: " + names.joined(separator: ", "))
        }
        addCaption(to: content, text: "Bestand: \(movie.fileName) — "
            + ByteCountFormatter.string(fromByteCount: movie.fileSize, countStyle: .file))
    }

    private func addCaption(to content: UIStackView, text: String) {
        let label = UILabel()
        label.text = text
        label.font = UIFont.systemFont(ofSize: 12)
        label.textColor = Theme.secondaryText
        label.numberOfLines = 0
        content.addArrangedSubview(label)
    }

    private func loadArtwork() {
        if let fanartPath = movie.fanartPath ?? movie.posterPath {
            ArtworkCache.shared.image(forSMBPath: fanartPath, maxPixelSize: 1000) { [weak self] image in
                self?.fanartView.image = image
            }
        }
        if let posterPath = movie.posterPath {
            ArtworkCache.shared.image(forSMBPath: posterPath, maxPixelSize: 500) { [weak self] image in
                self?.posterView.image = image
            }
        }
    }

    private func updatePlayButtons() {
        let hasProgress = ProgressStore.shared.fraction(for: movie) != nil
        playButton.setTitle(hasProgress ? "▶  Verder kijken" : "▶  Afspelen", for: .normal)
        restartButton.isHidden = !hasProgress
    }

    // MARK: - Acties

    @objc private func playTapped() {
        let player = PlayerViewController(movie: movie)
        player.modalPresentationStyle = .fullScreen
        present(player, animated: true)
    }

    @objc private func restartTapped() {
        ProgressStore.shared.clear(for: movie)
        updatePlayButtons()
        playTapped()
    }
}

/// Verloop van transparant naar zwart, voor over de fanart.
final class GradientView: UIView {
    override class var layerClass: AnyClass { CAGradientLayer.self }

    override init(frame: CGRect) {
        super.init(frame: frame)
        let gradient = layer as! CAGradientLayer
        gradient.colors = [UIColor.clear.cgColor,
                           UIColor.black.withAlphaComponent(0.55).cgColor,
                           UIColor.black.cgColor]
        gradient.locations = [0, 0.65, 1]
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }
}
