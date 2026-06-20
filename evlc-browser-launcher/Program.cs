using System.Diagnostics;

namespace EvlcBrowserLauncher;

internal static class Program
{
    private static int Main(string[] args)
    {
        var launcherDirectory = AppContext.BaseDirectory;
        var scriptPath = Path.GetFullPath(
            Environment.GetEnvironmentVariable("EVLC_SCRIPT")
            ?? Path.Combine(launcherDirectory, "evlc.py")
        );
        var errorLog = Path.Combine(launcherDirectory, "evlc-browser-error.log");

        try
        {
            if (!File.Exists(scriptPath))
            {
                throw new FileNotFoundException(
                    "Place evlc-browser.exe beside evlc.py, or set EVLC_SCRIPT.",
                    scriptPath
                );
            }

            var python = FindPythonw();
            var startInfo = new ProcessStartInfo
            {
                FileName = python,
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = launcherDirectory,
            };

            startInfo.ArgumentList.Add(scriptPath);
            foreach (var arg in args)
            {
                startInfo.ArgumentList.Add(arg);
            }

            Process.Start(startInfo);
            return 0;
        }
        catch (Exception exception)
        {
            File.AppendAllText(
                errorLog,
                $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {exception}\n"
            );
            return 1;
        }
    }

    private static string FindPythonw()
    {
        var configured = Environment.GetEnvironmentVariable("EVLC_PYTHONW");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var pythonRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "Python"
        );
        if (Directory.Exists(pythonRoot))
        {
            var installed = Directory
                .EnumerateFiles(pythonRoot, "pythonw.exe", SearchOption.AllDirectories)
                .OrderByDescending(path => path, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
            if (installed is not null)
            {
                return installed;
            }
        }

        // ProcessStartInfo will resolve this through PATH when Python is installed there.
        return "pythonw.exe";
    }
}
