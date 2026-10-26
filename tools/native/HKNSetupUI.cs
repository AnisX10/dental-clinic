// HKN Dentaire - setup wizard UI (WinForms, no COM beyond WScript.Shell shortcuts).
using System;
using System.Drawing;
using System.IO;
using System.Linq;
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
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (var f = new WizardForm()) Application.Run(f);
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

        // page state
        TextBox _tbLic;
        TextBox _tbPath; string _rootDir;
        TextBox _tbName; TextBox _tbUser; TextBox _tbPass; TextBox _tbPass2;
        CheckBox _cbDesktop; CheckBox _cbLan; CheckBox _cbLaunch;
        Label _log; string _installId;

        public WizardForm()
        {
            Text = "HKN Dentaire - Installation";
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
            Goto(0);
        }

        void Goto(int step)
        {
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
            _stack.Controls.Add(page);
            _stack.ResumeLayout();
            if (_step != 5)
            {
                _next.Enabled = _step < 5;
            }
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
                Text = "Bienvenue dans l'assistant d'installation de HKN Dentaire\n\n" +
                      "1) Choisissez où installer le programme (un sous-dossier sera créé).\n\n" +
                      "2) Important : choisissez le mot de passe que vous utiliserez chaque jour.\n\n" +
                      "3) L'installation est par utilisateur (pas d'administration requise) et se\n" +
                      "     termine par un lancement automatique de l'application.",
                Padding = new Padding(4),
            };
            return P(l);
        }

        Control BuildLicense()
        {
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 5, ColumnCount = 2 };
            _tbLic = new TextBox { Height = 22 };
            var licBtn = new Button { Text = "Parcourir…", Height = 26 };
            licBtn.Click += (s, e) =>
            {
                using (var dlg = new OpenFileDialog { Filter = "Licence (*.lic)|*.lic", Title = "Sélectionner la licence de la clinique" })
                    if (dlg.ShowDialog() == DialogResult.OK) _tbLic.Text = dlg.FileName;
            };
            p.Controls.Add(new Label { Text = "Fichier de licence (*.lic):", AutoSize = true, Height = 24 }, 0, 1);
            p.Controls.Add(_tbLic, 0, 2);
            p.Controls.Add(licBtn, 1, 2);
            return P(p);
        }

        Label PathWarn;
        Control BuildPath()
        {
            string def = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "HKN Dentaire");
            _tbPath = new TextBox { Text = def };
            PathWarn = new Label
            {
                Height = 44,
                ForeColor = Color.Firebrick,
                Text = "",
                Name = "PathWarn",
            };
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 6, ColumnCount = 2, AutoSize = true };
            p.Controls.Add(new Label { Text = "Dossier d'installation:", AutoSize = true, Height = 22 }, 0, 1);
            p.Controls.Add(_tbPath, 0, 2);
            _tbPath.Dock = DockStyle.Fill;
            var br = new Button { Text = "Parcourir…", Height = 26 };
            br.Click += (s, e) =>
            {
                using (var dlg = new FolderBrowserDialog()) if (dlg.ShowDialog() == DialogResult.OK) _tbPath.Text =dlg.SelectedPath;
            };
            p.Controls.Add(br, 1, 2);
            p.SetColumnSpan((Control)PathWarn, 2); p.Controls.Add((Control)PathWarn, 0, 3);
            _tbPath.TextChanged += (s, e) =>
            {
                string target = Path.Combine(ValidPath(_tbPath.Text), "scripts");
                PathWarn.Text = Directory.Exists(target)
                    ? "Un dossier d'installation existe déjà à cet emplacement.\nIl sera remplacé (vos données existantes sont conservées)."
                    : "";
            };
            return P(p);
        }

        static string ValidPath(string t)
        {
            try { return Path.GetFullPath(t.Trim()); }
            catch { return t.Trim(); }
        }

        Control BuildAccount()
        {
            var p = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
            int r = 0;
            GridLayoutAdd(p, new Label { Text = "Nom de la clinique:", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbName = new TextBox(), 0, r++);
            GridLayoutAdd(p, new Label { Text = "Nom d'utilisateur (login):", AutoSize = true, Height = 22 }, 0, r++);
            GridLayoutAdd(p, _tbUser = new TextBox(), 0, r++);
            GridLayoutAdd(p, new Label { Text = "Mot de passe (12+ caractères):", AutoSize = true, Height = 22 }, 0, r++);
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
                Text = "Autoriser l'accès depuis le réseau local (autres PC de la clinique) — nécessite une élevage d'administrateur",
                AutoSize = true,
                MaximumSize = new Size(560, 0),
            };
            _cbLaunch = new CheckBox { Text = "Lancer HKN Dentaire à la fin de l'installation", Checked = true, AutoSize = true };

            p.Controls.Add((Control)_cbDesktop, 0, 0);
            p.Controls.Add((Control)_cbLan, 0, 1);
            p.Controls.Add((Control)_cbLaunch, 0, 2);
            return P(p);
        }

        Control BuildInstall()
        {
            _log = new Label { Dock = DockStyle.Top, Height = 320, Font = new Font("Consolas", 9f), Text = "" };
            return P(_log);
        }

        Control BuildDone()
        {
            string idTxt = string.IsNullOrEmpty(_installId)
                ? "L'identient d'installation sera affiché dans l'application (Réglages → À propos)."
                : "Identifiant d'installation: " + _installId;

            var p = new TableLayoutPanel { Dock = DockStyle.Fill };
            p.Controls.Add(new Label
            {
                Dock = DockStyle.Top,
                Height = 100,
                Text = "Installation terminée\r\n\r\nL'application démarre à côté, dans la barre des tâches (près de l'horloge).\r\n" + idTxt,
            }, 0, 0);
            return P(p);
        }

        void OnNext()
        {
            if (_step == 1) { Goto(2); return; }
            if (_step == 2)
            {
                _rootDir = ValidPath(_tbPath.Text);
                if (string.IsNullOrWhiteSpace(_rootDir) || _rootDir.Length <= 3)
                { MessageBox.Show("Choisissez un dossier d'installation valide.", Text); return; }
                if (_rootDir.EndsWith(":", StringComparison.Ordinal))
                { MessageBox.Show("Choisissez un sous-dossier (pas la racine d'un disque).", Text); return; }
                Goto(3);
                return;
            }
            if (_step == 3)
            {
                string err = null;
                if (string.IsNullOrWhiteSpace(_tbName.Text)) err = "Saisissez le nom de la clinique.";
                if (err == null && string.IsNullOrWhiteSpace(_tbUser.Text)) err = "Saisissez le nom d'utilisateur.";
                if (err == null)
                {
                    string pw = _tbPass.Text;
                    if (pw.Length < 10) err = "Mot de passe: au moins 10 caractères.";
                    else if (!pw.Any(char.IsLetter) || !pw.Any(char.IsDigit)) err = "Mot de passe: lettres ET chiffres requis.";
                    else if (pw.All(c => char.IsLetterOrDigit(c))) err = "Mot de passe: ajoutez un symbole (! ? @ # - _).";
                    else if (pw.Equals(_tbName.Text, StringComparison.OrdinalIgnoreCase)) err = "Le mot de passe ne doit pas être le nom de la clinique.";
                    else if (_tbPass.Text != _tbPass2.Text) err = "Les deux mots de passe ne correspondent pas.";
                }
                if (err != null) { MessageBox.Show(err, Text); return; }
                Goto(4);
                return;
            }
            if (_step == 4) { Goto(5); RunInstall(); return; }
            if (_step == 6) { if (_cbLaunch.Checked) new Thread(OpenDone).Start(); Close(); }
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
            if (_step > 0 && _step < 5) Goto(_step - 1);
        }

        void LogLine(string s)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action(delegate { LogLine(s); }));
                return;
            }
            if (_log == null) return;
            _log.Text = _log.Text + s + "\r\n";
        }

        async void RunInstall()
        {
            string rootDir = _rootDir;
            string err = await Task.Run(new Func<string>(delegate
            {
                try
                {
                    LogLine("[1/8] Arrêt d'une installation en cours…");
                    try { Steps.KillProcessesUnder(rootDir); } catch (Exception) { }

                    LogLine("[2/8] Création des dossier…");
                    Directory.CreateDirectory(rootDir);
                    Directory.CreateDirectory(Path.Combine(rootDir, "data"));

                    LogLine("[3/8] Extraction de l'application (peut prendre une minute)…");
                    string e1 = Steps.ExtractZip(rootDir);
                    if (e1 != null) return e1;

                    LogLine("[4/8] Import de la licence…");
                    Steps.CopyLicense(_tbLic.Text, rootDir);

                    LogLine("[5/8] Création des raccourcis…");
                    Steps.MakeShortcuts(rootDir, _cbDesktop.Checked);

                    LogLine("[6/8] Initialisation de la base de données…");
                    string pw = _tbPass.Text;
                    string outp = Steps.InitProd(rootDir, _tbUser.Text.Trim(), pw, _tbName.Text.Trim(),
                        !File.Exists(Path.Combine(rootDir, "data", ".already_initialized")));
                    LogLine("        Base de données prête.");

                    LogLine("[7/8] " + (_cbLan.Checked ? "Ouverture du réseau local…" : "Réseau local: non demandé"));
                    Steps.RegisterUninstall(rootDir);
                    if (_cbLan.Checked) Steps.AllowLan();

                    try { _installId = Steps.ReadInstallationIdAt(rootDir); }
                    catch (Exception) { _installId = null; }

                    try { File.WriteAllText(Path.Combine(rootDir, "data", ".already_initialized"), "1"); }
                    catch { }

                    return null;
                }
                catch (Exception ex)
                {
                    return ex.Message;
                }
            }));

            BeginInvoke(new Action(delegate
            {
                if (err != null)
                {
                    LogLine("\r\nÉCHEC: " + err);
                    LogLine("(Détails complets dans %TEMP%\\hkn_setup_last_error.txt)");
                    _next.Visible = true;
                    _back.Visible = true;
                    _next.Text = "Terminer";
                    _step = 6;
                    return;
                }
                LogLine("\r\nTerminé.");
                Goto(6);
            }));
        }
    }
}
