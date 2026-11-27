// HKN Dentaire - tray launcher (daily use). Compiled with /define:HKN_TRAY
using System;
using System.Collections.Generic;
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

            // /background = Windows login (HKCU Run): tray + server only, no window.
            bool background = args != null && (Array.IndexOf(args, "/background") >= 0 || Array.IndexOf(args, "-background") >= 0);

            bool createdNew;
            _mutex = new Mutex(true, Common.MutexName, out createdNew);
            if (!createdNew)
            {
                if (background) return; // already running: nothing to show at login
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
            ctx.RunHeadless(background); // start server without blocking the tray
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
        ToolStripMenuItem _logsItem;
        ToolStripMenuItem _autostartItem;
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

        bool _quietStart; // background start: no splash, no app window until the user asks

        public void RunHeadless(bool background)
        {
            _quietStart = background;
            EnsureTray();
            if (background) TrayLog.Write("background start (Windows login): no window");
            else OpenAppAsync(); // the poller starts the server in both cases
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
            _logsItem = new ToolStripMenuItem("Ouvrir les journaux");
            _logsItem.Click += delegate { OpenLogsFolder(); };
            _autostartItem = new ToolStripMenuItem("Démarrer HKN Dentaire avec Windows");
            _autostartItem.Click += delegate { ToggleAutostart(); };
            _menu.Opening += delegate { RefreshAutostartItem(); };
            RefreshAutostartItem();
            _stopItem = new ToolStripMenuItem("Arrêter tout et quitter");
            _stopItem.Click += delegate { QuitFully(); };

            _menu.Items.Add(_statusItem);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add(_openItem);
            _menu.Items.Add(_consoleItem);
            _menu.Items.Add(_logsItem);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add(_autostartItem);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add(_stopItem);
            _tray.ContextMenuStrip = _menu;
            _tray.DoubleClick += delegate { OpenAppAsync(); };

            _poll = new System.Windows.Forms.Timer();
            _poll.Interval = 1500;
            _poll.Tick += PollTick;
            _poll.Start();

            // Logoff / shutdown: stop PostgreSQL cleanly instead of letting Windows kill it.
            Microsoft.Win32.SystemEvents.SessionEnding += OnSessionEnding;
            TrayLog.Write("tray launcher started");

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

        // --- crash recovery -------------------------------------------------
        // Failed health probes in a row (while online) before we restart.
        // A dead process is restarted quickly; a process that is still alive
        // but not answering (busy backup, long query) gets much more slack so
        // we never kill a server that is merely slow.
        const int CrashFailThreshold = 3;   // ~5 s at 1.5 s polling
        const int HungFailThreshold = 20;   // ~30-50 s
        const int BackoffStartMs = 2000;
        const int BackoffMaxMs = 60000;
        const int SupportRestartCount = 3;
        static readonly TimeSpan SupportWindow = TimeSpan.FromMinutes(10);

        int _failCount;
        int _backoffMs;
        DateTime _nextStartUtc = DateTime.MinValue;
        bool _restarting;          // kill in progress on a worker thread
        bool _hadOutage;           // logged "back online" once recovered
        volatile bool _shuttingDown;
        readonly List<DateTime> _restartTimes = new List<DateTime>();
        DateTime _lastSupportBalloonUtc = DateTime.MinValue;

        void PollTick(object sender, EventArgs e)
        {
            if (_shuttingDown || _restarting) return;
            bool aliveCommon = Common.HealthProbe(900);
            if (aliveCommon)
            {
                _failCount = 0;
                _backoffMs = 0;   // healthy again: next restart starts from 2 s
                if (_state != 2)
                {
                    _state = 2;
                    if (_tray != null)
                    {
                        _tray.Text = Common.AppName + " — en ligne";
                        _statusItem.Text = "Statut: application en ligne ✔";
                    }
                    if (_status != null) { _status.Done(); _status = null; }
                    _quietStart = false; // later restarts show the splash again
                    TrayLog.Write(_hadOutage ? "server back online after restart" : "server online");
                    _hadOutage = false;
                }
                return;
            }
            bool procAlive = _server != null && !_server.HasExited;
            if (_state == 2)
            {
                // Was online, probe failed: crash or hang.
                _failCount++;
                int threshold = procAlive ? HungFailThreshold : CrashFailThreshold;
                if (_failCount >= threshold) BeginRestart(procAlive);
                return;
            }
            if (procAlive && _state == 1) return; // still starting
            if (_state == 1 && !procAlive)
            {
                // Start attempt exited before the server became healthy.
                string code = "?";
                try { if (_server != null) code = _server.ExitCode.ToString(System.Globalization.CultureInfo.InvariantCulture); }
                catch (Exception) { }
                int delay = NextBackoff();
                TrayLog.Write("start attempt exited before becoming healthy (exit code " + code + "); retry in " + (delay / 1000) + " s");
                _state = 0;
                _nextStartUtc = DateTime.UtcNow.AddMilliseconds(delay);
                RecordRestart();
                return;
            }
            if (_state == 0 && DateTime.UtcNow >= _nextStartUtc) StartServerProc();  // cold start / retry after backoff
        }

        int NextBackoff()
        {
            _backoffMs = _backoffMs <= 0 ? BackoffStartMs : Math.Min(_backoffMs * 2, BackoffMaxMs);
            return _backoffMs;
        }

        void BeginRestart(bool hung)
        {
            _restarting = true;
            _hadOutage = true;
            _state = 0;
            _failCount = 0;
            int delay = NextBackoff();
            if (_tray != null)
            {
                _tray.Text = Common.AppName + " — redémarrage…";
                _statusItem.Text = "Statut: redémarrage du serveur…";
            }
            TrayLog.Write((hung ? "server not responding (process alive)" : "server crashed (process gone)") +
                "; killing and restarting in " + (delay / 1000) + " s");
            RecordRestart();

            var server = _server;
            _server = null;
            ThreadPool.QueueUserWorkItem(delegate
            {
                // WMI lookups and the gentle stop take seconds: keep them off the UI thread.
                KillServerTree(server, true);
                try
                {
                    _invoker.BeginInvoke((MethodInvoker)delegate
                    {
                        _nextStartUtc = DateTime.UtcNow.AddMilliseconds(delay);
                        _restarting = false;
                    });
                }
                catch (Exception)
                {
                    _nextStartUtc = DateTime.UtcNow.AddMilliseconds(delay);
                    _restarting = false;
                }
            });
        }

        // gentle: if our python is still running, stop PostgreSQL cleanly and give
        // python up to 10 s before killing (crash case: python is gone, so this
        // costs nothing). Then kill the cmd.exe wrapper's whole tree, and sweep
        // any python.exe still running our launcher.py (cmd already exited, or
        // the server was started by another process).
        static void KillServerTree(Process server, bool gentle)
        {
            if (gentle)
            {
                try
                {
                    string what = Common.KillOwnServerProcess(Common.RootDir, true, Common.GentleExitWaitMs);
                    if (what != null) TrayLog.Write("gentle stop: " + what);
                }
                catch (Exception) { }
            }
            try
            {
                if (server != null && !server.HasExited)
                {
                    Common.RunHidden("taskkill.exe", "/T /F /PID " +
                        server.Id.ToString(System.Globalization.CultureInfo.InvariantCulture), 15000);
                }
            }
            catch (Exception) { }
            try { Common.KillOwnServerProcess(Common.RootDir, false, 0); }
            catch (Exception) { }
            try { if (server != null) server.Dispose(); }
            catch (Exception) { }
        }

        void RecordRestart()
        {
            var now = DateTime.UtcNow;
            _restartTimes.Add(now);
            _restartTimes.RemoveAll(t => now - t > SupportWindow);
            if (_restartTimes.Count >= SupportRestartCount && now - _lastSupportBalloonUtc > SupportWindow)
            {
                _lastSupportBalloonUtc = now;
                TrayLog.Write("repeated restarts: " + _restartTimes.Count + " in the last 10 minutes; support balloon shown");
                Notify("HKN Dentaire — problème détecté",
                    "Le serveur a dû redémarrer " + _restartTimes.Count + " fois en 10 minutes.\n" +
                    "Veuillez contacter le support HKN Dentaire.\n(Journal : data\\logs\\tray.log)");
            }
        }

        void OnSessionEnding(object sender, Microsoft.Win32.SessionEndingEventArgs e)
        {
            if (_shuttingDown) return;
            _shuttingDown = true; // stops PollTick from restarting the server mid-shutdown
            TrayLog.Write("session ending (" + e.Reason + "): stopping server and database");
            // We are inside a synchronous WM_QUERYENDSESSION: COM calls (the WMI
            // lookups in KillOwnServerProcess) are refused on this thread with
            // RPC_E_CANTCALLOUT_ININPUTSYNCCALL. Do the work on a worker thread
            // and block here until it is done (pg_ctl stop is bounded at 45 s).
            var server = _server;
            var worker = new Thread(delegate ()
            {
                // Fast path: clean PostgreSQL stop, then kill python right away
                // (Windows only waits a few seconds before forcing the logoff).
                try { Common.GracefulStop(Common.RootDir, 0); }
                catch (Exception) { }
                KillServerTree(server, false);
            });
            worker.IsBackground = true;
            worker.Start();
            bool finished = worker.Join(TimeSpan.FromSeconds(60));
            TrayLog.Write(finished ? "graceful stop finished" : "graceful stop still running after 60 s");
        }

        void StartServerProc()
        {
            _state = 1;
            if (_tray != null)
            {
                _tray.Text = Common.AppName + " — démarrage...";
                _statusItem.Text = "Statut: démarrage de la base de données...";
            }
            if (!_quietStart) ShowStatusWindow();
            try
            {
                _server = Common.StartServerHidden();
                TrayLog.Write("server process started (pid " + _server.Id + ")");
            }
            catch (Exception ex)
            {
                _server = null;
                TrayLog.Write("could not start server process: " + ex.Message);
            }
        }

        void ShowStatusWindow()
        {
            if (_status != null && !_status.IsDisposed) return;
            try
            {
                _status = new StatusWindow();
                _status.Show();
            }
            catch (Exception ex)
            {
                // Cosmetic only: never let the splash window block a server start.
                _status = null;
                TrayLog.Write("status window failed: " + ex.Message);
            }
        }

        public void OpenAppAsync()
        {
            _quietStart = false; // the user asked for the app
            ThreadPool.QueueUserWorkItem(delegate
            {
                bool ok = Common.HealthProbe(900);
                if (!ok)
                {
                    // The UI-thread poller owns every server start (backoff, restart
                    // sweep, single instance); here we only nudge it and wait.
                    try
                    {
                        _invoker.BeginInvoke((MethodInvoker)delegate
                        {
                            if (_shuttingDown || _restarting) return;
                            if (_state != 1 && (_server == null || _server.HasExited))
                            {
                                _state = 0;
                                _nextStartUtc = DateTime.MinValue; // user asked: skip the backoff wait
                            }
                        });
                    }
                    catch (Exception) { }
                    var deadline = DateTime.UtcNow.AddSeconds(90);
                    while (DateTime.UtcNow < deadline)
                    {
                        if (Common.HealthProbe(500)) break;
                        Thread.Sleep(600);
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

        void OpenLogsFolder()
        {
            string dir = Path.Combine(Common.RootDir, "data", "logs");
            try
            {
                Directory.CreateDirectory(dir);
                Process.Start(new ProcessStartInfo("explorer.exe", "\"" + dir + "\"") { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Notify(Common.AppName, "Impossible d'ouvrir le dossier des journaux :\n" + dir + "\n" + ex.Message);
            }
        }

        void RefreshAutostartItem()
        {
            try { _autostartItem.Checked = Common.IsAutostartEnabled(Common.RootDir); }
            catch (Exception) { }
        }

        void ToggleAutostart()
        {
            bool want = !Common.IsAutostartEnabled(Common.RootDir);
            string err = Common.SetAutostart(Common.RootDir, want);
            RefreshAutostartItem();
            TrayLog.Write("start with Windows " + (want ? "enabled" : "disabled") + " from tray menu" + (err != null ? " FAILED: " + err : ""));
            if (err != null)
                Notify(Common.AppName, "Le réglage « Démarrer avec Windows » n'a pas pu être modifié :\n" + err);
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
            _shuttingDown = true;
            _poll.Stop();
            try { Microsoft.Win32.SystemEvents.SessionEnding -= OnSessionEnding; }
            catch (Exception) { }
            TrayLog.Write("quit requested from tray menu");
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

    // Append-only diagnostic log at <root>\data\logs\tray.log, kept under 1 MB
    // by dropping the oldest half when it grows too big. Never throws.
    internal static class TrayLog
    {
        const long MaxBytes = 1024 * 1024;
        static readonly object Gate = new object();

        static string LogPath
        {
            get { return Path.Combine(Common.RootDir, "data", "logs", "tray.log"); }
        }

        public static void Write(string message)
        {
            try
            {
                lock (Gate)
                {
                    string path = LogPath;
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    string line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", System.Globalization.CultureInfo.InvariantCulture) +
                        "  " + message + "\r\n";
                    var fi = new FileInfo(path);
                    if (fi.Exists && fi.Length + line.Length * 3 > MaxBytes) TruncateOldestHalf(path);
                    File.AppendAllText(path, line, new System.Text.UTF8Encoding(false));
                }
            }
            catch (Exception) { }
        }

        static void TruncateOldestHalf(string path)
        {
            byte[] all = File.ReadAllBytes(path);
            int start = all.Length / 2;
            while (start < all.Length && all[start] != (byte)'\n') start++;
            start = Math.Min(start + 1, all.Length); // cut on a line boundary (UTF-8 safe)
            using (var fs = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.Read))
            {
                fs.Write(all, start, all.Length - start);
            }
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
