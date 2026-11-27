// HKN Dentaire - setup wizard UI (WinForms, no COM beyond WScript.Shell shortcuts).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace HKN
{
    internal static class SetupEntry
    {
        [STAThread]
        static void Main(string[] args)
        {
            bool created;
            using (var mutex = new Mutex(true, "HKN.Dentaire.Setup", out created))
            {
                if (!created)
                {
                    MessageBox.Show("L'assistant d'installation de HKN Dentaire est déjà ouvert.", "HKN Dentaire",
                        MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                Steps.Log("==== Setup HKN Dentaire " + BuildInfo.Version + " démarré ====");
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                using (var f = new WizardForm()) Application.Run(f);
                GC.KeepAlive(mutex);
            }
        }
    }

    // Production password policy, ported from backend/app/cli.py
    // _prod_password_problem (the weak list is generated from it at build time).
    internal static class PasswordPolicy
    {
        const string AsciiLetters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
        const string AsciiPunctuation = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";

        // null = accepted, otherwise the French reason.
        public static string Problem(string password)
        {
            password = password ?? "";
            int length = 0; // Python len() counts code points, not UTF-16 units
            foreach (char c in password) if (!char.IsLowSurrogate(c)) length++;
            if (length < 10)
                return "au moins 10 caractères (actuellement " + length + ").";
            if (PasswordPolicyData.Weak.Contains(password.ToLowerInvariant()))
                return "trop courant / facile à deviner.";
            bool letter = password.Any(c => AsciiLetters.IndexOf(c) >= 0);
            bool digit = password.Any(char.IsDigit);
            bool symbol = password.Any(c => AsciiPunctuation.IndexOf(c) >= 0);
            if (!(letter && digit && symbol))
                return "mélangez des lettres, des chiffres et un symbole (ex. Dr#-cabinet-2026).";
            return null;
        }
    }

    internal class WizardForm : Form
    {
        readonly Panel _stack;
        readonly Button _next = new Button();
        readonly Button _back = new Button();
        readonly Button _cancel = new Button();
        readonly Label _hint = new Label();
        int _step;
        bool _failed;
        bool _installing;
        bool _existingInstall;
        float _dpiScale = 1f;
        bool _loaded;

        // page state (kept across Back/Next)
        TextBox _tbKey; string _keyText = "";
        TextBox _tbPath; string _rootDir;
        TextBox _tbName; TextBox _tbUser; TextBox _tbPass; TextBox _tbPass2;
        CheckBox _cbDesktop; CheckBox _cbLan; CheckBox _cbLaunch; CheckBox _cbAutostart;
        bool? _autostartUserChoice; // set once the user clicks the box (survives Back/Next)
        Label _log; string _installId;
        readonly List<string> _warnings = new List<string>();
        int _port = Common.DefaultPort;
        string _lanResult;

        public WizardForm()
        {
            // The exe is DPI-aware (manifest): fonts are in points and follow the
            // DPI, so pixel sizes are scaled explicitly (WinForms autoscale does
            // not run for this code-built form).
            AutoScaleMode = AutoScaleMode.None;
            try { using (var g = Graphics.FromHwnd(IntPtr.Zero)) _dpiScale = g.DpiX / 96f; }
            catch (Exception) { _dpiScale = 1f; }
            Text = "HKN Dentaire " + BuildInfo.Version + " - Installation";
            Font = new Font("Segoe UI", 9.5f);
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(640, 480);
            ClientSize = new Size(620, 470);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;

            _stack = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24) };
            Controls.Add(_stack);

            _next.Text = "Suivant >";
            _back.Text = "< Retour";
            _cancel.Text = "Annuler";
            _next.DialogResult = DialogResult.None;
            _next.Click += (s, e) => OnNext();
            _back.Click += (s, e) => { OnBack(); };
            _cancel.Click += (s, e) => Close();
            var bottom = new FlowLayoutPanel
            {
                Dock = DockStyle.Bottom,
                Height = 44,
                FlowDirection = FlowDirection.RightToLeft,
                Padding = new Padding(8, 6, 12, 6),
            };
            bottom.Controls.Add(_next);
            bottom.Controls.Add(_back);
            bottom.Controls.Add(_cancel);
            _next.TabStop = true;
            Controls.Add(bottom);

            _hint.Dock = DockStyle.Bottom;
            _hint.Height = 24;
            _hint.Padding = new Padding(12, 2, 0, 0);
            _hint.ForeColor = Color.DimGray;
            Controls.Add(_hint);

            AcceptButton = _next;
            FormClosing += OnFormClosing;
            Goto(0);
            if (Math.Abs(_dpiScale - 1f) > 0.01f) Scale(new SizeF(_dpiScale, _dpiScale)); // window, buttons, first page
            _loaded = true; // later pages are scaled one by one in Goto
        }

        void OnFormClosing(object sender, FormClosingEventArgs e)
        {
            if (_installing)
            {
                e.Cancel = true;
                MessageBox.Show("L'installation est en cours. Merci de patienter jusqu'à la fin : l'interrompre maintenant " +
                                "pourrait laisser l'application inutilisable.", Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        void Goto(int step)
        {
            if (_step == 1 && _tbKey != null) _keyText = _tbKey.Text;
            if (_step == 2 && _tbPath != null) _rootDir = ValidPath(_tbPath.Text);
            _step = step;
            _stack.SuspendLayout();
            _stack.Controls.Clear();
            Control page;
            switch (step)
            {
                case 0: page = BuildWelcome(); break;
                case 1: page = BuildLicense(); break;
                case 2: page = BuildPath(); break;
                case 3: page = BuildAccount(); break;
                case 4: page = BuildOptions(); break;
                case 5: page = BuildInstall(); _next.Visible = false; _back.Visible = false; break;
                default: page = BuildDone(); break;
            }
            // pages built after the form's own DPI autoscale need scaling too
            if (_loaded && Math.Abs(_dpiScale - 1f) > 0.01f) page.Scale(new SizeF(_dpiScale, _dpiScale));
            _stack.Controls.Add(page);
            _stack.ResumeLayout();
            _next.Visible = _step != 5;
            _back.Visible = _step > 0 && _step < 5;
            _cancel.Enabled = _step != 5;
            _next.Enabled = _step < 5 || _step == 6;
            _next.Text = (_step == 4) ? "Installer" : (_step == 6 ? "Terminer" : "Suivant >");
        }

        Control P(Control padding)
        {
            padding.Dock = DockStyle.Fill;
            var host = new Panel { Dock = DockStyle.Fill, AutoScroll = true, Padding = new Padding(0, 10, 6, 6) };
            host.Controls.Add(padding);
            return host;
        }

        Control BuildWelcome()
        {
            var l = new Label
            {
                Dock = DockStyle.Fill,
                Text = "Bienvenue dans l'assistant d'installation de HKN Dentaire " + BuildInfo.Version + "\n\n" +
                      "1) Choisissez où installer le programme (un sous-dossier sera créé).\n\n" +
                      "2) Important : choisissez le mot de passe que vous utiliserez chaque jour.\n\n" +
                      "3) L'installation est par utilisateur (pas d'administration requise) et se\n" +
                      "     termine par un lancement automatique de l'application.\n\n" +
                      "Une installation existante est mise à jour en conservant toutes les données.",
                Padding = new Padding(4),
            };
            return P(l);
        }

        Control BuildLicense()
        {
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 5, ColumnCount = 1 };
            _tbKey = new TextBox
            {
                Multiline = true,
                Height = 64,
                Font = new Font("Consolas", 10f),
                ScrollBars = ScrollBars.Vertical,
                WordWrap = false,
                Text = _keyText,
            };
            p.Controls.Add(new Label
            {
                AutoSize = true,
                Height = 24,
                Text = "Clé de licence (fournie par votre revendeur, commence par HKN1.) :",
            }, 0, 0);
            p.Controls.Add(_tbKey, 0, 1);
            p.SetRowSpan(_tbKey, 3);
            p.Controls.Add(new Label
            {
                Dock = DockStyle.Top,
                Height = 40,
                ForeColor = Color.DimGray,
                Text = "Optionnel : collez la clé sur une seule ligne. Sans clé, l'application\naffichera l'écran d'activation à la première ouverture. Sur une mise à jour,\nla licence existante est conservée; utilisez l'écran Licence pour la changer.",
            }, 0, 4);
            return P(p);
        }

        // ------------------------------------------------------------ path page
        Label PathWarn;
        Control BuildPath()
        {
            string def = _rootDir;
            string note = null;
            if (string.IsNullOrEmpty(def))
            {
                string registered = Steps.RegisteredInstallLocation();
                if (registered != null && Directory.Exists(registered) && NonAsciiProblem(registered) == null) def = registered; // upgrade
                else
                {
                    def = registered != null && Directory.Exists(registered)
                        ? registered
                        : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", AppFolderName);
                    string problem = PathProblem(def);
                    if (problem != null)
                    {
                        note = "Emplacement par défaut remplacé par C:\\" + AppFolderName + " : " + problem;
                        Steps.Log(note + " (" + def + ")");
                        def = @"C:\" + AppFolderName;
                    }
                }
            }
            _tbPath = new TextBox();
            PathWarn = new Label
            {
                Height = 64,
                ForeColor = Color.Firebrick,
                Text = "",
                Name = "PathWarn",
                Dock = DockStyle.Fill,
            };
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 6, ColumnCount = 2, AutoSize = true };
            p.Controls.Add(new Label { Text = "Dossier d'installation:", AutoSize = true, Height = 22 }, 0, 1);
            p.Controls.Add(_tbPath, 0, 2);
            _tbPath.Dock = DockStyle.Fill;
            var br = new Button { Text = "Parcourir…", Height = 26 };
            br.Click += (s, e) =>
            {
                using (var dlg = new FolderBrowserDialog())
                {
                    if (dlg.ShowDialog() != DialogResult.OK) return;
                    string picked = WithAppFolder(dlg.SelectedPath);
                    if (RefuseNonAscii(picked)) return;
                    _tbPath.Text = picked;
                }
            };
            p.Controls.Add(br, 1, 2);
            p.SetColumnSpan((Control)PathWarn, 2); p.Controls.Add((Control)PathWarn, 0, 3);
            if (note != null)
            {
                var noteLabel = new Label { Text = note, ForeColor = Color.DarkGoldenrod, Height = 44, Dock = DockStyle.Fill };
                p.SetColumnSpan(noteLabel, 2); p.Controls.Add(noteLabel, 0, 4);
            }
            _tbPath.TextChanged += (s, e) => UpdatePathWarn();
            _tbPath.Text = def;
            UpdatePathWarn(); // also for the default path
            return P(p);
        }

        void UpdatePathWarn()
        {
            string root = ValidPath(_tbPath.Text);
            var lines = new List<string>();
            if (IsExistingHknInstall(root) || IsPartialHknInstall(root))
            {
                string v = Steps.InstalledVersion(root);
                lines.Add("Une installation existe déjà à cet emplacement" + (v != null ? " (version " + v + ")" : "") +
                          ".\nElle sera mise à jour (vos données existantes sont conservées).");
            }
            else if (!IsEmptyOrMissing(root))
                lines.Add("Ce dossier n'est pas vide : choisissez un dossier vide\nou ajoutez « \\" + AppFolderName + " » à la fin du chemin.");
            string problem = PathProblem(root);
            if (problem != null) lines.Add("Attention : " + problem);
            PathWarn.Text = string.Join("\n", lines);
        }

        // HARD rule: the bundled PostgreSQL binaries live under the install root
        // and read their own path through ANSI APIs, then hand it to SQL as UTF-8:
        // any non-ASCII character (é, ç, Arabic…) makes initdb fail. Same rule as
        // the backend guard app.core.db.unsupported_path_chars.
        static string NonAsciiProblem(string path)
        {
            if (string.IsNullOrEmpty(path)) return null;
            foreach (char c in path)
                if (c > 127)
                    return "le chemin contient le caractère « " + c + " ». La base de données exige un chemin sans accents " +
                           "ni lettres non latines (souvent à cause du nom d'utilisateur Windows).";
            return null;
        }

        // Refuses a non-ASCII root with a short explanation and pre-fills the
        // safe location. Returns true when the path was refused.
        bool RefuseNonAscii(string root)
        {
            string problem = NonAsciiProblem(root);
            if (problem == null) return false;
            Steps.Log("chemin refusé (non ASCII): " + root);
            MessageBox.Show("Ce dossier ne peut pas être utilisé :\n" + root + "\n\n" +
                            char.ToUpperInvariant(problem[0]) + problem.Substring(1) +
                            "\n\nLe dossier C:\\" + AppFolderName + " a été proposé à la place.",
                            Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            _tbPath.Text = @"C:\" + AppFolderName;
            return true;
        }

        // Locations where the bundled PostgreSQL/Python are known to break.
        static string PathProblem(string path)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(path)) return null;
                string nonAscii = NonAsciiProblem(path);
                if (nonAscii != null) return nonAscii;
                foreach (string env in new[] { "OneDrive", "OneDriveConsumer", "OneDriveCommercial" })
                {
                    string od = Environment.GetEnvironmentVariable(env);
                    if (!string.IsNullOrEmpty(od) &&
                        (path.Equals(od, StringComparison.OrdinalIgnoreCase) ||
                         path.StartsWith(od.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase)))
                        return "dossier synchronisé par OneDrive (risque de corruption de la base de données).";
                }
                if (path.IndexOf("\\OneDrive", StringComparison.OrdinalIgnoreCase) >= 0)
                    return "dossier synchronisé par OneDrive (risque de corruption de la base de données).";
                if (path.StartsWith(@"\\", StringComparison.Ordinal))
                    return "dossier réseau : installez sur le disque local du PC.";
                var drive = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(path)));
                if (drive.DriveType == DriveType.Network) return "lecteur réseau : installez sur le disque local du PC.";
                if (drive.DriveType == DriveType.Removable) return "disque amovible (clé USB…) : installez sur le disque local du PC.";
            }
            catch (Exception) { }
            return null;
        }

        static string ValidPath(string t)
        {
            try
            {
                string full = Path.GetFullPath((t ?? "").Trim());
                string root = Path.GetPathRoot(full);
                if (!string.Equals(full, root, StringComparison.OrdinalIgnoreCase))
                    full = full.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                return full;
            }
            catch { return (t ?? "").Trim(); }
        }

        const string AppFolderName = "HKN Dentaire";

        // A browsed folder is the PARENT the user picked (e.g. Documents): always
        // install into a dedicated "HKN Dentaire" sub-folder so uninstall can
        // never touch the user's other files.
        static string WithAppFolder(string selected)
        {
            string full = ValidPath(selected ?? "");
            if (full.Length == 0) return full;
            string name = Path.GetFileName(full.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
            if (string.Equals(name, AppFolderName, StringComparison.OrdinalIgnoreCase)) return full;
            return Path.Combine(full, AppFolderName);
        }

        // Existing HKN install = HKN database (data\pgdata\PG_VERSION) or the
        // Setup marker. App files are usually there too, but an uninstall that
        // kept the data leaves only data\, and reinstalling over it must work.
        internal static bool IsExistingHknInstall(string root)
        {
            try
            {
                return File.Exists(Path.Combine(root, "data", "pgdata", "PG_VERSION")) ||
                       File.Exists(Path.Combine(root, "data", ".already_initialized"));
            }
            catch (Exception) { return false; }
        }

        // Our own half-finished install (extraction completed, init failed):
        // the payload manifest plus the launcher are present.
        static bool IsPartialHknInstall(string root)
        {
            try
            {
                return File.Exists(Path.Combine(root, Steps.ManifestName)) &&
                       File.Exists(Path.Combine(root, "scripts", "HKN Dentaire.exe"));
            }
            catch (Exception) { return false; }
        }

        static bool IsEmptyOrMissing(string dir)
        {
            try { return !Directory.Exists(dir) || !Directory.EnumerateFileSystemEntries(dir).Any(); }
            catch (Exception) { return false; }
        }

        // ------------------------------------------------------------ other pages
        Control BuildAccount()
        {
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
            int r = 0;
            GridLayoutAdd(p, new Label { Text = "Nom complet du dentiste:", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbName = new TextBox(), 0, r++);
            GridLayoutAdd(p, new Label { Text = "Nom d'utilisateur (login):", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbUser = new TextBox(), 0, r++);
            GridLayoutAdd(p, new Label { Text = "Mot de passe (10+ caractères, lettres + chiffres + symbole):", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbPass = new TextBox { UseSystemPasswordChar = true }, 0, r++);
            GridLayoutAdd(p, new Label { Text = "Confirmer le mot de passe:", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbPass2 = new TextBox { UseSystemPasswordChar = true }, 0, r++);
            GridLayoutAdd(p, new Label { Text = "Ce mot de passe sera demandé à chaque ouverture de l'application.", ForeColor = Color.DimGray, Height = 24 }, 0, r++);
            return P(p);
        }

        static void GridLayoutAdd(TableLayoutPanel p, Control c, int col, int row)
        {
            c.Dock = DockStyle.Fill;
            p.Controls.Add(c, col, row);
        }

        Control BuildOptions()
        {
            var p = new TableLayoutPanel { Dock = DockStyle.Fill };

            _cbDesktop = new CheckBox { Text = "Créer un raccourci « HKN Dentaire » sur le Bureau", Checked = true, AutoSize = true };
            _cbLan = new CheckBox
            {
                Text = "Autoriser l'accès depuis le réseau local (autres PC de la clinique)\n" +
                       "— nécessite une élévation d'administrateur (règle de pare-feu)",
                AutoSize = true,
                Checked = _existingInstall && Common.ReadLan(_rootDir),
            };
            _cbLaunch = new CheckBox { Text = "Lancer HKN Dentaire à la fin de l'installation", Checked = true, AutoSize = true };

            // Start with Windows: an upgrade keeps the existing setting; a fresh
            // install follows "réseau local" (other PCs need the server running)
            // until the user ticks/unticks it themselves.
            bool autostartDefault = _existingInstall ? Common.IsAutostartEnabled(_rootDir) : _cbLan.Checked;
            _cbAutostart = new CheckBox
            {
                Text = "Démarrer HKN Dentaire avec Windows\n" +
                       "— en arrière-plan, sans fenêtre (conseillé si d'autres PC s'y connectent)",
                AutoSize = true,
                Checked = _autostartUserChoice ?? autostartDefault,
            };
            _cbAutostart.Click += delegate { _autostartUserChoice = _cbAutostart.Checked; };
            _cbLan.CheckedChanged += delegate
            {
                if (!_existingInstall && _autostartUserChoice == null) _cbAutostart.Checked = _cbLan.Checked;
            };

            int row = 0;
            if (_existingInstall)
            {
                string from = Steps.InstalledVersion(_rootDir);
                string to = Steps.PayloadVersion();
                p.Controls.Add(new Label
                {
                    Text = "Mise à jour" + (from != null && to != null ? " " + from + " → " + to : "") +
                           " : les comptes, mots de passe, données et la licence sont conservés.\n" +
                           "Une sauvegarde vérifiée est faite automatiquement au premier démarrage.",
                    AutoSize = true,
                    ForeColor = Color.DimGray,
                    MaximumSize = new Size(560, 0),
                }, 0, row++);
            }
            p.Controls.Add((Control)_cbDesktop, 0, row++);
            p.Controls.Add((Control)_cbLan, 0, row++);
            p.Controls.Add((Control)_cbAutostart, 0, row++);
            p.Controls.Add((Control)_cbLaunch, 0, row++);
            return P(p);
        }

        Control BuildInstall()
        {
            _log = new Label { Dock = DockStyle.Top, Height = 340, Font = new Font("Consolas", 9f), Text = "" };
            return P(_log);
        }

        Control BuildDone()
        {
            var sb = new StringBuilder();
            sb.Append(_existingInstall ? "Mise à jour terminée" : "Installation terminée").Append("\r\n\r\n");
            sb.Append("Cliquez sur Terminer pour fermer l'assistant. Si vous avez choisi le lancement automatique, l'application démarre à côté de l'horloge.\r\n\r\n");
            sb.Append(string.IsNullOrEmpty(_installId)
                ? "L'identifiant d'installation sera affiché dans Paramètres → Licence."
                : "Identifiant d'installation: " + _installId).Append("\r\n");
            sb.Append("Adresse locale : http://127.0.0.1:" + _port).Append("\r\n");
            if (_lanResult != null) sb.Append("Réseau local : " + _lanResult).Append("\r\n");
            if (_warnings.Count > 0)
            {
                sb.Append("\r\nAvertissements :\r\n");
                foreach (string w in _warnings) sb.Append("  • " + w + "\r\n");
                sb.Append("(journal complet : " + Steps.LogPath + ")");
            }
            var p = new TableLayoutPanel { Dock = DockStyle.Fill };
            p.Controls.Add(new Label { Dock = DockStyle.Fill, AutoSize = false, Height = 300, Text = sb.ToString() }, 0, 0);
            return P(p);
        }

        // ------------------------------------------------------------ navigation
        void OnNext()
        {
            if (_step == 0) { Goto(1); return; }
            if (_step == 1)
            {
                string key = _tbKey.Text.Trim();
                if (key.Length > 0 && !key.StartsWith("HKN1.", StringComparison.Ordinal))
                {
                    MessageBox.Show("La clé de licence doit commencer par HKN1. (collez la ligne complète reçue du revendeur).", Text);
                    return;
                }
                Goto(2);
                return;
            }
            if (_step == 2)
            {
                string root = ValidPath(_tbPath.Text);
                if (string.IsNullOrWhiteSpace(root) || root.Length <= 3)
                { MessageBox.Show("Choisissez un dossier d'installation valide.", Text); return; }
                string pathRoot = Path.GetPathRoot(root);
                if (string.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                    pathRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                    StringComparison.OrdinalIgnoreCase))
                { MessageBox.Show("Choisissez un sous-dossier (pas la racine d'un disque).", Text); return; }
                if (File.Exists(root))
                { MessageBox.Show("Ce chemin désigne un fichier, pas un dossier.", Text); return; }
                if (RefuseNonAscii(root)) return; // hard rule, never overridable
                bool existing = IsExistingHknInstall(root);
                if (!existing && !IsPartialHknInstall(root) && !IsEmptyOrMissing(root))
                {
                    string suggestion = WithAppFolder(root);
                    MessageBox.Show(
                        "Le dossier choisi n'est pas vide et ne contient pas une installation HKN Dentaire :\n" + root +
                        "\n\nPour protéger vos fichiers, choisissez un dossier vide ou un nouveau dossier" +
                        (string.Equals(suggestion, root, StringComparison.OrdinalIgnoreCase) ? "." : ", par exemple :\n" + suggestion),
                        Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    if (!string.Equals(suggestion, root, StringComparison.OrdinalIgnoreCase)) _tbPath.Text = suggestion;
                    return;
                }
                string problem = PathProblem(root);
                if (problem != null &&
                    MessageBox.Show("Emplacement déconseillé : " + problem + "\n\nRecommandé : C:\\" + AppFolderName +
                                    "\n\nContinuer quand même avec ce dossier ?", Text, MessageBoxButtons.YesNo,
                                    MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
                    return;
                string payloadVersion;
                try { Payload.Slice(); payloadVersion = Steps.PayloadVersion(); }
                catch (Exception ex)
                {
                    Steps.Log("payload: " + ex);
                    MessageBox.Show(ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
                if (existing)
                {
                    string installed = Steps.InstalledVersion(root);
                    if (installed != null && payloadVersion != null && Steps.CompareVersions(payloadVersion, installed) < 0)
                    {
                        Steps.Log("rétrogradation refusée: installé " + installed + ", paquet " + payloadVersion);
                        MessageBox.Show(
                            "Une version plus récente de HKN Dentaire est déjà installée dans ce dossier.\n\n" +
                            "Version installée : " + installed + "\nVersion de ce programme d'installation : " + payloadVersion + "\n\n" +
                            "Revenir à une version antérieure n'est pas possible : la base de données a déjà été mise à jour " +
                            "et ne serait plus lisible. Utilisez le programme d'installation de la version " + installed +
                            " ou d'une version plus récente.",
                            Text, MessageBoxButtons.OK, MessageBoxIcon.Stop);
                        return;
                    }
                }
                _rootDir = root;
                _existingInstall = existing;
                Steps.Log("dossier: " + root + (existing ? " (installation existante " + (Steps.InstalledVersion(root) ?? "?") + ")" : " (nouvelle installation)"));
                Goto(_existingInstall ? 4 : 3);
                return;
            }
            if (_step == 3)
            {
                string err = null;
                if (string.IsNullOrWhiteSpace(_tbName.Text)) err = "Saisissez le nom complet du dentiste.";
                if (err == null && string.IsNullOrWhiteSpace(_tbUser.Text)) err = "Saisissez le nom d'utilisateur.";
                if (err == null)
                {
                    string problem = PasswordPolicy.Problem(_tbPass.Text);
                    if (problem != null) err = "Mot de passe refusé : " + problem;
                    else if (_tbPass.Text != _tbPass2.Text) err = "Les deux mots de passe ne correspondent pas.";
                }
                if (err != null) { MessageBox.Show(err, Text); return; }
                Goto(4);
                return;
            }
            if (_step == 4) { Goto(5); RunInstall(); return; }
            if (_step == 6)
            {
                if (!_failed && _cbLaunch.Checked) new Thread(OpenDone).Start();
                Close();
            }
        }

        void OpenDone()
        {
            try
            {
                string rootDir = _rootDir;
                string exe = Path.Combine(rootDir, "scripts", "HKN Dentaire.exe");
                if (File.Exists(exe))
                {
                    var psi = new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = exe,
                        WorkingDirectory = Path.Combine(rootDir, "scripts"),
                        UseShellExecute = true,
                    };
                    System.Diagnostics.Process.Start(psi);
                }
            }
            catch { }
        }

        void OnBack()
        {
            if (_step == 4 && _existingInstall) { Goto(2); return; }
            if (_step > 0 && _step < 5) Goto(_step - 1);
        }

        void LogLine(string s)
        {
            Steps.Log(s.Trim());
            if (InvokeRequired)
            {
                BeginInvoke(new Action(delegate { ShowLogLine(s); }));
                return;
            }
            ShowLogLine(s);
        }

        void ShowLogLine(string s)
        {
            if (_log == null) return;
            // a progress line ("        … …") replaces the previous progress line
            const string progress = "        …";
            string text = _log.Text;
            if (s.StartsWith(progress, StringComparison.Ordinal))
            {
                int cut = text.LastIndexOf("\r\n" + progress, StringComparison.Ordinal);
                if (cut >= 0 && text.IndexOf("\r\n", cut + 2, StringComparison.Ordinal) == text.Length - 2)
                    text = text.Substring(0, cut + 2);
            }
            _log.Text = text + s + "\r\n";
        }

        async void RunInstall()
        {
            string rootDir = _rootDir;
            bool existingInstall = _existingInstall;
            string keyText = _keyText;
            string username = existingInstall ? "" : _tbUser.Text.Trim();
            string password = existingInstall ? "" : _tbPass.Text;
            string fullName = existingInstall ? "" : _tbName.Text.Trim();
            bool desktop = _cbDesktop.Checked;
            bool allowLan = _cbLan.Checked;
            bool autostart = _cbAutostart.Checked;
            _installing = true;
            _warnings.Clear();
            string err = await Task.Run(new Func<string>(delegate
            {
                try
                {
                    string payloadVersion = Steps.PayloadVersion();
                    Steps.Log((existingInstall ? "mise à jour" : "installation") + " -> " + rootDir + ", version " + (payloadVersion ?? "?"));

                    LogLine("[1/8] Arrêt de HKN Dentaire s'il est ouvert…");
                    Steps.KillProcessesUnder(rootDir);

                    LogLine("[2/8] Création des dossiers…");
                    Directory.CreateDirectory(rootDir);
                    Directory.CreateDirectory(Path.Combine(rootDir, "data"));

                    LogLine("[3/8] " + (existingInstall ? "Remplacement des fichiers de l'application…" : "Extraction de l'application (peut prendre une minute)…"));
                    string e1 = Steps.InstallFiles(rootDir, LogLine);
                    if (e1 != null) return e1;

                    LogLine("[4/8] Clé de licence…");
                    if (existingInstall)
                        LogLine("        Installation existante : licence conservée.");
                    else if (!string.IsNullOrWhiteSpace(keyText))
                    {
                        string bad = Steps.VerifyKey(rootDir, keyText);
                        if (bad == null) { Steps.SaveKey(keyText, rootDir); LogLine("        Clé valide, enregistrée."); }
                        else
                        {
                            _warnings.Add("clé de licence non enregistrée : " + bad + ". Collez-la à nouveau dans l'écran d'activation.");
                            LogLine("        Clé refusée : " + bad);
                        }
                    }
                    else LogLine("        Aucune clé saisie (écran d'activation au premier lancement).");

                    if (!existingInstall)
                    {
                        LogLine("[5/8] Initialisation de la base de données (jusqu'à quelques minutes)…");
                        Steps.InitProd(rootDir, username, password, fullName, LogLine);
                        LogLine("        Base de données prête.");
                    }
                    else
                    {
                        LogLine("[5/8] Installation existante : comptes et données conservés (sauvegarde + migration au démarrage).");
                    }

                    LogLine("[6/8] Configuration réseau…");
                    _port = Steps.WriteConfig(rootDir, allowLan);
                    LogLine("        Port " + _port + (_port != Common.DefaultPort ? " (8000 était occupé)" : "") + ", réseau local : " + (allowLan ? "oui" : "non"));

                    LogLine("[7/8] Raccourcis et enregistrement Windows…");
                    foreach (string w in Steps.MakeShortcuts(rootDir, desktop)) { _warnings.Add(w); LogLine("        Avertissement : " + w); }
                    Steps.RegisterUninstall(rootDir, payloadVersion);
                    string autoErr = Common.SetAutostart(rootDir, autostart);
                    if (autoErr != null)
                    {
                        _warnings.Add("démarrage avec Windows non configuré : " + autoErr);
                        LogLine("        Avertissement : démarrage avec Windows non configuré : " + autoErr);
                    }
                    else LogLine("        Démarrage avec Windows : " + (autostart ? "oui (en arrière-plan)" : "non"));

                    LogLine("[8/8] Pare-feu…");
                    if (allowLan)
                    {
                        string fw = Firewall.Add(rootDir);
                        _lanResult = fw == null
                            ? "autorisé (règle de pare-feu « " + Firewall.RuleName + " », réseaux privés et de domaine)"
                            : "règle de pare-feu NON créée : " + fw;
                        if (fw != null) _warnings.Add("accès réseau local : " + fw);
                        LogLine("        " + _lanResult);
                    }
                    else
                    {
                        string fw = Firewall.RemoveFor(rootDir);
                        LogLine("        Réseau local non demandé" + (fw != null ? " (ancienne règle non supprimée : " + fw + ")" : "."));
                    }

                    try { _installId = Steps.ReadInstallationIdAt(rootDir); }
                    catch (Exception) { _installId = null; }

                    try { File.WriteAllText(Path.Combine(rootDir, "data", ".already_initialized"), "1"); }
                    catch { }

                    Steps.Log("terminé" + (_warnings.Count > 0 ? " avec " + _warnings.Count + " avertissement(s)" : ""));
                    return null;
                }
                catch (Exception ex)
                {
                    Steps.Log("ÉCHEC: " + ex);
                    return ex.Message;
                }
            }));

            BeginInvoke(new Action(delegate
            {
                _installing = false;
                if (err != null)
                {
                    LogLine("\r\nÉCHEC: " + err);
                    LogLine("(Journal complet : " + Steps.LogPath + ")");
                    _failed = true;
                    _next.Visible = true;
                    _back.Visible = false;
                    _cancel.Enabled = true;
                    _next.Enabled = true;
                    _next.Text = "Fermer";
                    _step = 6;
                    return;
                }
                LogLine("\r\nTerminé.");
                _failed = false;
                Goto(6);
            }));
        }
    }
}
