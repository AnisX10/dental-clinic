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
        public const int Port = 8000;
        public const string AppName = "HKN Dentaire";
        public const string MutexName = "HKN.Dentaire.Instance";
        public const string ShowAppEventName = "HKN.Dentaire.ShowApp";

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
            // pg_ctl clean stop of the bundled database, no force.
            RunHidden(BackendPython, "\"" + Path.Combine(RootDir, "backend", "app", "cli.py") + "\" stop-server", 45000);
            KillOwnServerProcess();
        }

        public static void KillOwnServerProcess()
        {
            try
            {
                foreach (var proc in Process.GetProcessesByName("python"))
                {
                    try
                    {
                        string cl = CommandLineOf(proc.Id);
                        if (!string.IsNullOrEmpty(cl) &&
                            (cl.IndexOf(Path.Combine(RootDir, "backend", "app", "launcher.py"), StringComparison.OrdinalIgnoreCase) >= 0
                             || cl.IndexOf("app\\launcher.py", StringComparison.OrdinalIgnoreCase) >= 0))
                        {
                            if (!proc.HasExited) proc.Kill();
                        }
                    }
                    finally { proc.Dispose(); }
                }
            }
            catch (Exception) { }
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
                    using (var s = StreamForIcon())
                    {
                        var ico = s != null ? new System.Drawing.Icon(s) : System.Drawing.Icon.ExtractAssociatedIcon(
                            System.Reflection.Assembly.GetExecutingAssembly().Location);
                        _bitmap96 = new System.Drawing.Bitmap(96, 96);
                        using (var g = System.Drawing.Graphics.FromImage(_bitmap96))
                        {
                            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
                            g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
                            g.Clear(System.Drawing.Color.White);
                            g.DrawIcon(ico, new System.Drawing.Rectangle(2, 2, 92, 92));
                        }
                    }
                }
                return _bitmap96;
            }
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
