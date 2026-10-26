// HKN Dentaire - tray launcher (daily use). Compiled with /define:HKN_TRAY
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace HKN
{
    static class LauncherEntry
    {
        static Mutex _mutex;
        static EventWaitHandle _showRequest;

        [STAThread]
        static void Main(string[] args)
        {
            if (args != null && args.Length > 0)
            {
                if (Array.IndexOf(args, "/uninstall") >= 0 || Array.IndexOf(args, "-uninstall") >= 0)
                {
                    UninstallRunner.Run();
                    return;
                }
                if (Array.IndexOf(args, "/selfdelete") >= 0 || Array.IndexOf(args, "-selfdelete") >= 0)
                {
                    SelfDelete.Run(args);
                    return;
                }
            }

            bool createdNew;
            _mutex = new Mutex(true, Common.MutexName, out createdNew);
            if (!createdNew)
            {
                // Another instance is running: ask it to bring the app window up.
                try
                {
                    var ev = EventWaitHandle.OpenExisting(Common.ShowAppEventName);
                    ev.Set();
                }
                catch (Exception) { }
                return;
            }
            _showRequest = new EventWaitHandle(false, EventResetMode.AutoReset, Common.ShowAppEventName);
            LauncherContext.SetShowRequest(_showRequest);

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            var ctx = new LauncherContext();
            if (args != null && Array.IndexOf(args, "/console") >= 0)
            {
                Process.Start(new ProcessStartInfo("cmd.exe", "/k chcp 65001 >nul & \"" + Common.BackendPython +
                    "\" \"" + Path.Combine(Common.RootDir, "backend", "app", "launcher.py") + "\"") { WorkingDirectory = Common.RootDir, UseShellExecute = true });
                return;
            }
            if (args != null && Array.IndexOf(args, "/stop") >= 0)
            {
                Common.GracefulStop();
                return;
            }
            ctx.RunHeadless();          // start server without blocking the tray
            Application.Run(ctx);       // tray icon pumps until Quit
            GC.KeepAlive(_mutex);
        }
    }

    internal class LauncherContext : ApplicationContext
    {
        static EventWaitHandle _showRequest;
        static Form _invoker; // hidden handle owner for cross-thread marshalling

        public static void SetShowRequest(EventWaitHandle ev)
        {
            _showRequest = ev;
        }

        NotifyIcon _tray;
        ContextMenuStrip _menu;
        ToolStripMenuItem _statusItem;
        ToolStripMenuItem _openItem;
        ToolStripMenuItem _consoleItem;
        ToolStripMenuItem _stopItem;
        System.Windows.Forms.Timer _poll;
        StatusWindow _status;
        Process _server;
        int _state; // 0=down,1=starting,2=running

        public LauncherContext()
        {
            _invoker = new Form { FormBorderStyle = FormBorderStyle.None, ShowInTaskbar = false, Visible = false, Opacity = 0 };
            var unused = _invoker.Handle; // force handle creation on the UI thread
        }

        public new void ExitThread()
        {
            base.ExitThread();
        }

        public void RunHeadless()
        {
            EnsureTray();
            OpenAppAsync();
        }

        void EnsureTray()
        {
            _tray = new NotifyIcon();
            _tray.Icon = HKN.Icons.TrayIcon;
            _tray.Text = Common.AppName;
            _tray.Visible = true;

            _menu = new ContextMenuStrip();
            _statusItem = new ToolStripMenuItem("Statut: démarrage...");
            _statusItem.Enabled = false;
            _openItem = new ToolStripMenuItem("Ouvrir HKN Dentaire");
            _openItem.Font = new System.Drawing.Font(_openItem.Font, System.Drawing.FontStyle.Bold);
            _openItem.Click += delegate { OpenAppAsync(); };
            _consoleItem = new ToolStripMenuItem("Console de diagnostic...");
            _consoleItem.Click += delegate { OpenConsole(); };
            _stopItem = new ToolStripMenuItem("Arrêter tout et quitter");
            _stopItem.Click += delegate { QuitFully(); };

            _menu.Items.Add(_statusItem);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add(_openItem);
            _menu.Items.Add(_consoleItem);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add(_stopItem);
            _tray.ContextMenuStrip = _menu;
            _tray.DoubleClick += delegate { OpenAppAsync(); };

            _poll = new System.Windows.Forms.Timer();
            _poll.Interval = 1500;
            _poll.Tick += PollTick;
            _poll.Start();

            var showTimer = new System.Windows.Forms.Timer();
            showTimer.Interval = 700;
            showTimer.Tick += delegate
            {
                try
                {
                    if (_showRequest.WaitOne(0)) OpenAppAsync();
                }
                catch (Exception) { }
            };
            showTimer.Start();
        }

        void PollTick(object sender, EventArgs e)
        {
            bool aliveCommon = Common.HealthProbe(900);
            if (aliveCommon)
            {
                if (_state != 2)
                {
                    _state = 2;
                    if (_tray != null)
                    {
                        _tray.Text = Common.AppName + " — en ligne";
                        _statusItem.Text = "Statut: application en ligne ✔";
                    }
                    if (_status != null) { _status.Done(); _status = null; }
                }
                return;
            }
            bool procAlive = _server != null && !_server.HasExited;
            if (_state == 2 || (procAlive && _state == 1)) return; // still starting
            if (_state == 0 || (_state == 1 && !procAlive)) StartServerProc();  // cold start / retry
        }

        void StartServerProc()
        {
            _state = 1;
            if (_tray != null)
            {
                _tray.Text = Common.AppName + " — démarrage...";
                _statusItem.Text = "Statut: démarrage de la base de données...";
            }
            ShowStatusWindow();
            _server = Common.StartServerHidden();
        }

        void ShowStatusWindow()
        {
            if (_status != null && !_status.IsDisposed) return;
            _status = new StatusWindow();
            _status.Show();
        }

        public void OpenAppAsync()
        {
            ThreadPool.QueueUserWorkItem(delegate
            {
                bool ok = Common.HealthProbe(900);
                if (!ok)
                {
                    if (_server == null || _server.HasExited)
                    {
                        _state = 0; // so PollTick can relaunch
                    }
                    // wait for the poller to bring it up
                    var deadline = DateTime.UtcNow.AddSeconds(90);
                    while (DateTime.UtcNow < deadline)
                    {
                        if (Common.HealthProbe(500)) break;
                        Thread.Sleep(600);
                        if (_server == null || _server.HasExited)
                        {
                            try
                            {
                                _server = Common.StartServerHidden();
                            }
                            catch (Exception) { return; }
                        }
                    }
                }
                try
                {
                    _invoker.BeginInvoke((MethodInvoker)delegate
                    {
                        if (Common.HealthProbe(700)) Common.OpenApp();
                        else Notify("HKN Dentaire", "Le serveur n'a pas pu démarrer.\n\nDouble-cliquez sur l'icône pour réessayer, ou lancez scripts\\start.bat pour voir le message d'erreur.");
                    });
                }
                catch (Exception) { }
            });
        }

        void Notify(string title, string text)
        {
            try
            {
                _tray.BalloonTipTitle = title;
                _tray.BalloonTipText = text;
                _tray.ShowBalloonTip(8000);
            }
            catch (Exception) { }
        }

        void OpenConsole()
        {
            Process.Start(new ProcessStartInfo("cmd.exe",
                "/k chcp 65001 >nul & \"" + Common.BackendPython + "\" \"" +
                Path.Combine(Common.RootDir, "backend", "app", "launcher.py") + "\"")
            { WorkingDirectory = Common.RootDir, UseShellExecute = true });
        }

        void QuitFully()
        {
            if (MessageBox.Show(
                "Voulez-vous fermer HKN Dentaire ?\n\nLe serveur local et la base de données seront arrêtés proprement.",
                Common.AppName, MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK)
                return;
            _poll.Stop();
            _tray.Visible = false;
            var stopItem = _stopItem;
            ThreadPool.QueueUserWorkItem(delegate
            {
                try { Common.GracefulStop(); }
                catch (Exception) { }
                try { Common.KillOwnServerProcess(); }
                catch (Exception) { }
                try
                {
                    _invoker.BeginInvoke((MethodInvoker)delegate
                    {
                        stopItem.Text = "Arrêt terminé.";
                        Application.Exit();
                    });
                }
                catch (Exception) { Application.Exit(); }
            });
        }
    }

    internal class StatusWindow : Form
    {
        public StatusWindow()
        {
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            ShowInTaskbar = false;
            TopMost = true;
            Size = new System.Drawing.Size(420, 120);
            BackColor = System.Drawing.Color.White;

            var icon = new PictureBox();
            icon.Image = HKN.Icons.Bitmap96;
            icon.Location = new System.Drawing.Point(14, 14);
            icon.Size = new System.Drawing.Size(64, 64);
            icon.SizeMode = PictureBoxSizeMode.StretchImage;
            icon.BackColor = System.Drawing.Color.Transparent;
            Controls.Add(icon);

            var title = new System.Windows.Forms.Label();
            title.Text = "HKN Dentaire";
            title.Font = new System.Drawing.Font("Segoe UI Semibold", 13F);
            title.Location = new System.Drawing.Point(92, 14);
            title.Size = new System.Drawing.Size(310, 26);
            title.BackColor = System.Drawing.Color.Transparent;
            Controls.Add(title);

            var label = new System.Windows.Forms.Label();
            label.Text = "Ouverture de la base de données locale...\n(le premier lancement prend quelques secondes)";
            label.Font = new System.Drawing.Font("Segoe UI", 9F);
            label.Location = new System.Drawing.Point(92, 40);
            label.Size = new System.Drawing.Size(310, 40);
            label.ForeColor = System.Drawing.Color.FromArgb(90, 90, 90);
            label.BackColor = System.Drawing.Color.White;
            Controls.Add(label);

            var progress = new System.Windows.Forms.ProgressBar();
            progress.Style = ProgressBarStyle.Marquee;
            progress.MarqueeAnimationSpeed = 40;
            progress.Location = new System.Drawing.Point(16, 88);
            progress.Size = new System.Drawing.Size(388, 10);
            Controls.Add(progress);
            progress.BringToFront();

            Click += delegate { };
            DoubleBuffered = true;
        }

        public void Done()
        {
            try { Close(); } catch (Exception) { }
        }
    }
}
