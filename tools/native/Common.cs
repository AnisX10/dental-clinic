// HKN Dentaire - shared native helpers (compiled against .NET Framework 4.8, C# 5)
// Used by both the tray launcher (HKN Dentaire.exe) and the one-file installer.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading;

namespace HKN
{
    public static class Common
    {
        public const int DefaultPort = 8000;

        // data\config.json = {"port": 8000, "lan": false}, written by Setup and
        // read by the launcher/scripts. Missing file or keys -> 8000 / false.
        public static int Port
        {
            get { return ReadPort(RootDir); }
        }

        public static int ReadPort(string root)
        {
            string json = ReadConfigText(root);
            var m = System.Text.RegularExpressions.Regex.Match(json ?? "", "\"port\"\\s*:\\s*(\\d{1,5})");
            int port;
            if (m.Success && int.TryParse(m.Groups[1].Value, out port) && port > 0 && port < 65536) return port;
            return DefaultPort;
        }

        public static bool ReadLan(string root)
        {
            string json = ReadConfigText(root);
            return System.Text.RegularExpressions.Regex.IsMatch(json ?? "", "\"lan\"\\s*:\\s*true");
        }

        public static string ConfigPath(string root)
        {
            return Path.Combine(root, "data", "config.json");
        }

        static string ReadConfigText(string root)
        {
            try
            {
                string p = ConfigPath(root);
                return File.Exists(p) ? File.ReadAllText(p) : null;
            }
            catch (Exception) { return null; }
        }
        public const string AppName = "HKN Dentaire";
        public const string MutexName = "HKN.Dentaire.Instance";
        public const string ShowAppEventName = "HKN.Dentaire.ShowApp";

        // --- start with Windows (HKCU Run, per user, no elevation) -----------
        public const string AutostartValueName = "HKN Dentaire";
        const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";

        public static string LauncherExe(string root)
        {
            return Path.Combine(root, "scripts", "HKN Dentaire.exe");
        }

        public static string AutostartCommand(string root)
        {
            return "\"" + LauncherExe(root) + "\" /background";
        }

        // Raw Run value, or null when absent.
        public static string ReadAutostartValue()
        {
            try
            {
                using (var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(RunKeyPath, false))
                    return key == null ? null : key.GetValue(AutostartValueName) as string;
            }
            catch (Exception) { return null; }
        }

        // True when the Run value exists and starts THIS installation.
        public static bool IsAutostartEnabled(string root)
        {
            string v = ReadAutostartValue();
            return v != null && v.IndexOf(LauncherExe(root), StringComparison.OrdinalIgnoreCase) >= 0;
        }

        // Returns null on success, else a short error message.
        public static string SetAutostart(string root, bool enabled)
        {
            try
            {
                if (!enabled) { RemoveAutostartFor(root); return null; }
                using (var key = Microsoft.Win32.Registry.CurrentUser.CreateSubKey(RunKeyPath))
                    key.SetValue(AutostartValueName, AutostartCommand(root), Microsoft.Win32.RegistryValueKind.String);
                return null;
            }
            catch (Exception ex) { return ex.Message; }
        }

        // Deletes the Run value only if it points at this installation (another
        // install on the same account keeps its own setting).
        public static void RemoveAutostartFor(string root)
        {
            try
            {
                if (!IsAutostartEnabled(root)) return;
                using (var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(RunKeyPath, true))
                    if (key != null) key.DeleteValue(AutostartValueName, false);
            }
            catch (Exception) { }
        }

        public static string RootDir
        {
            get
            {
                // exe lives in <root>\scripts -> root is its parent
                return Path.GetDirectoryName(AppDir);
            }
        }

        public static string AppDir
        {
            get
            {
                string loc = System.Reflection.Assembly.GetExecutingAssembly().Location;
                return Path.GetDirectoryName(loc);
            }
        }

        public static string RuntimePython
        {
            get { return Path.Combine(RootDir, "runtime", "python.exe"); }
        }

        public static string VenvPython
        {
            get { return Path.Combine(RootDir, ".venv", "Scripts", "python.exe"); }
        }

        public static string BackendPython
        {
            get { return File.Exists(RuntimePython) ? RuntimePython : VenvPython; }
        }

        public static bool RuntimeReady
        {
            get { return File.Exists(BackendPython) && File.Exists(Path.Combine(RootDir, "backend", "app", "main.py")); }
        }

        public static string BuildUrl()
        {
            return "http://127.0.0.1:" + Port.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }

        public static bool HealthProbe(int timeoutMs)
        {
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(BuildUrl() + "/api/health");
                req.Timeout = timeoutMs;
                req.Method = "GET";
                req.UserAgent = "HKNLauncher/1.0";
                using (var resp = (HttpWebResponse)req.GetResponse())
                {
                    if (resp.StatusCode == HttpStatusCode.OK)
                    {
                        using (var st = resp.GetResponseStream())
                        using (var sr = new StreamReader(st))
                        {
                            string body = sr.ReadToEnd();
                            return body.IndexOf("\"ok\":true", StringComparison.OrdinalIgnoreCase) >= 0
                                || body.IndexOf("\"ok\": true", StringComparison.OrdinalIgnoreCase) >= 0;
                        }
                    }
                }
            }
            catch (Exception) { }
            return false;
        }

        public static Process StartServerHidden()
        {
            var psi = new ProcessStartInfo();
            psi.FileName = "cmd.exe";
            psi.Arguments = "/c chcp 65001 >nul & \"" + BackendPython + "\" \"" +
                Path.Combine(RootDir, "backend", "app", "launcher.py") + "\" --no-pause --no-browser";
            psi.WorkingDirectory = RootDir;
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            return Process.Start(psi);
        }

        public static bool RunHidden(string fileName, string args, int timeoutMs)
        {
            var psi = new ProcessStartInfo();
            psi.FileName = fileName;
            psi.Arguments = args;
            psi.WorkingDirectory = RootDir;
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            try
            {
                using (var p = Process.Start(psi))
                {
                    return p.WaitForExit(timeoutMs) && p.ExitCode == 0;
                }
            }
            catch (Exception)
            {
                return false;
            }
        }

        public static void GracefulStop()
        {
            GracefulStop(RootDir);
        }

        // Same, for an explicit install root (used by Setup, whose exe is not
        // inside the installation).
        public static void GracefulStop(string root)
        {
            GracefulStop(root, GentleExitWaitMs);
        }

        // waitForExitMs: how long python gets to exit on its own after the
        // database stopped (0 = kill right away, used at logoff when time is short).
        public static void GracefulStop(string root, int waitForExitMs)
        {
            StopDatabase(root); // pg_ctl clean stop of the bundled database, no force.
            KillOwnServerProcess(root, false, waitForExitMs);
        }

        public const int GentleExitWaitMs = 10000;

        // Runs `cli.py stop-server` (clean PostgreSQL shutdown). True if it ran and exited 0.
        public static bool StopDatabase(string root)
        {
            string py = Path.Combine(root, "runtime", "python.exe");
            if (!File.Exists(py)) py = Path.Combine(root, ".venv", "Scripts", "python.exe"); // dev checkout
            string cli = Path.Combine(root, "backend", "app", "cli.py");
            if (!File.Exists(py) || !File.Exists(cli)) return false;
            var psi = new ProcessStartInfo(py, "\"" + cli + "\" stop-server")
            {
                WorkingDirectory = root,
                CreateNoWindow = true,
                UseShellExecute = false,
            };
            try
            {
                using (var p = Process.Start(psi))
                    return p.WaitForExit(45000) && p.ExitCode == 0;
            }
            catch (Exception) { return false; }
        }

        public static void KillOwnServerProcess()
        {
            KillOwnServerProcess(RootDir);
        }

        // Gentle by default: if our server is running, stop PostgreSQL cleanly
        // first, give python up to 10 s to exit, and only then kill it.
        public static void KillOwnServerProcess(string root)
        {
            KillOwnServerProcess(root, true, GentleExitWaitMs);
        }

        // Returns null when no server process was found, else a one-line summary
        // of what happened (for tray.log / the setup log).
        public static string KillOwnServerProcess(string root, bool stopDatabaseFirst, int waitForExitMs)
        {
            var procs = FindOwnServerProcesses(root);
            if (procs.Count == 0) return null;
            var sw = Stopwatch.StartNew();
            string db = "not requested";
            int exited = 0, killed = 0;
            try
            {
                if (stopDatabaseFirst) db = StopDatabase(root) ? "stopped cleanly" : "stop failed or not running";
                var deadline = DateTime.UtcNow.AddMilliseconds(Math.Max(0, waitForExitMs));
                foreach (var proc in procs)
                {
                    try
                    {
                        int left = (int)Math.Max(0, (deadline - DateTime.UtcNow).TotalMilliseconds);
                        if (proc.HasExited || proc.WaitForExit(left)) exited++;
                        else { proc.Kill(); killed++; }
                    }
                    catch (Exception) { }
                }
            }
            finally
            {
                foreach (var proc in procs) proc.Dispose();
            }
            return "database " + db + "; python: " + exited + " exited, " + killed + " killed (" +
                (sw.ElapsedMilliseconds / 1000.0).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture) + " s)";
        }

        // python.exe processes running this installation's backend\app\launcher.py.
        // Uses WMI: do not call from inside a synchronous window message (logoff).
        public static List<Process> FindOwnServerProcesses(string root)
        {
            var found = new List<Process>();
            try
            {
                string launcherScript = Path.GetFullPath(Path.Combine(root, "backend", "app", "launcher.py"));
                foreach (var proc in Process.GetProcessesByName("python"))
                {
                    bool keep = false;
                    try
                    {
                        string cl = CommandLineOf(proc.Id);
                        keep = !string.IsNullOrEmpty(cl) && cl.IndexOf(launcherScript, StringComparison.OrdinalIgnoreCase) >= 0;
                    }
                    catch (Exception) { }
                    if (keep) found.Add(proc); else proc.Dispose();
                }
            }
            catch (Exception) { }
            return found;
        }

        public static string CommandLineOf(int pid)
        {
            try
            {
                using (var searcher = new System.Management.ManagementObjectSearcher(
                    "SELECT CommandLine FROM Win32_Process WHERE ProcessId = " + pid.ToString(System.Globalization.CultureInfo.InvariantCulture)))
                {
                    foreach (var o in searcher.Get())
                    {
                        using (o)
                        {
                            var v = o["CommandLine"] as string;
                            if (!string.IsNullOrEmpty(v)) return v;
                        }
                    }
                }
            }
            catch (Exception) { }
            return null;
        }

        public static string FindBrowserWindowMode(bool appMode)
        {
            // Returns full command to open the app window, or null for default browser.
            string[] browsers = new string[]
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                    "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                    "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Microsoft", "Edge", "Application", "msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                    "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                    "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Google", "Chrome", "Application", "chrome.exe"),
            };
            foreach (var b in browsers)
            {
                if (File.Exists(b)) return "\"" + b + "\" " + (appMode ? "--app=" : "") + BuildUrl();
            }
            return null;
        }

        public static void OpenApp()
        {
            string cmd = FindBrowserWindowMode(true);
            if (cmd != null)
            {
                RunHidden("cmd.exe", "/c start \"\" " + cmd, 15000);
            }
            else
            {
                try
                {
                    Process.Start(new ProcessStartInfo(BuildUrl()) { UseShellExecute = true });
                }
                catch (Exception) { }
            }
        }

        public static string ReadInstallationId()
        {
            try
            {
                var psi = new ProcessStartInfo();
                psi.FileName = BackendPython;
                psi.Arguments = "\"" + Path.Combine(RootDir, "backend", "app", "cli.py") + "\" print-installation-id --json";
                psi.WorkingDirectory = RootDir;
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                using (var p = Process.Start(psi))
                {
                    string outp = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(30000);
                    var hit = outp.IndexOf("\"installation\"", StringComparison.OrdinalIgnoreCase);
                    if (hit < 0) return null;
                    int start = outp.IndexOf('"', hit + 14);
                    int end = outp.IndexOf('"', start + 1);
                    if (start < 0 || end < 0) return null;
                    return outp.Substring(start + 1, end - start - 1);
                }
            }
            catch (Exception) { }
            return null;
        }
    }

    public static class Icons
    {
        static System.Drawing.Icon _trayIcon;
        static System.Drawing.Bitmap _bitmap96;

        public static System.Drawing.Icon TrayIcon
        {
            get
            {
                if (_trayIcon == null)
                {
                    using (var s = StreamForIcon())
                    {
                        if (s != null) _trayIcon = new System.Drawing.Icon(s);
                        else _trayIcon = System.Drawing.Icon.ExtractAssociatedIcon(
                            System.Reflection.Assembly.GetExecutingAssembly().Location);
                    }
                }
                return (System.Drawing.Icon)_trayIcon.Clone();
            }
        }

        public static System.Drawing.Bitmap Bitmap96
        {
            get
            {
                if (_bitmap96 == null)
                {
                    var bmp = new System.Drawing.Bitmap(96, 96);
                    using (var g = System.Drawing.Graphics.FromImage(bmp))
                    {
                        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
                        g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
                        g.Clear(System.Drawing.Color.White);
                        var rect = new System.Drawing.Rectangle(2, 2, 92, 92);
                        // app.ico frames are PNG-compressed: .NET Framework's Icon drawing
                        // (DrawIcon/ToBitmap) throws on those, so decode the PNG ourselves.
                        try
                        {
                            using (var png = LargestPngFrame())
                            {
                                if (png != null) g.DrawImage(png, rect);
                                else
                                {
                                    using (var ico = System.Drawing.Icon.ExtractAssociatedIcon(
                                        System.Reflection.Assembly.GetExecutingAssembly().Location))
                                        g.DrawIcon(ico, rect);
                                }
                            }
                        }
                        catch (Exception) { } // a blank tile is better than a crash
                    }
                    _bitmap96 = bmp;
                }
                return _bitmap96;
            }
        }

        // Returns the biggest PNG-encoded frame of the embedded app.ico, or null.
        static System.Drawing.Bitmap LargestPngFrame()
        {
            byte[] ico;
            using (var s = StreamForIcon())
            {
                if (s == null) return null;
                using (var ms = new MemoryStream())
                {
                    s.CopyTo(ms);
                    ico = ms.ToArray();
                }
            }
            if (ico.Length < 6) return null;
            int count = BitConverter.ToUInt16(ico, 4);
            int bestSize = -1, bestOff = 0, bestLen = 0;
            for (int i = 0; i < count; i++)
            {
                int e = 6 + 16 * i;
                if (e + 16 > ico.Length) break;
                int w = ico[e] == 0 ? 256 : ico[e];
                int len = (int)BitConverter.ToUInt32(ico, e + 8);
                int off = (int)BitConverter.ToUInt32(ico, e + 12);
                if (off < 0 || len <= 8 || off + len > ico.Length) continue;
                bool isPng = ico[off] == 0x89 && ico[off + 1] == (byte)'P' && ico[off + 2] == (byte)'N' && ico[off + 3] == (byte)'G';
                if (isPng && w > bestSize) { bestSize = w; bestOff = off; bestLen = len; }
            }
            if (bestSize < 0) return null;
            using (var ms = new MemoryStream(ico, bestOff, bestLen))
            using (var img = System.Drawing.Image.FromStream(ms))
                return new System.Drawing.Bitmap(img); // copy: detach from the stream
        }

        static System.IO.Stream StreamForIcon()
        {
            var asm = System.Reflection.Assembly.GetExecutingAssembly();
            var names = asm.GetManifestResourceNames();
            foreach (var n in names)
            {
                if (n.EndsWith("app.ico", System.StringComparison.OrdinalIgnoreCase))
                    return asm.GetManifestResourceStream(n);
            }
            return null;
        }
    }
}
