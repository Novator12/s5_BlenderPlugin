param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RestartManagerQuery
{
    private const int CCH_RM_SESSION_KEY = 32;
    private const int CCH_RM_MAX_APP_NAME = 255;
    private const int CCH_RM_MAX_SVC_NAME = 63;
    private const int ERROR_MORE_DATA = 234;

    [StructLayout(LayoutKind.Sequential)]
    public struct RM_UNIQUE_PROCESS
    {
        public int dwProcessId;
        public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct RM_PROCESS_INFO
    {
        public RM_UNIQUE_PROCESS Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_APP_NAME + 1)]
        public string strAppName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_SVC_NAME + 1)]
        public string strServiceShortName;
        public uint ApplicationType;
        public uint AppStatus;
        public uint TSSessionId;
        [MarshalAs(UnmanagedType.Bool)]
        public bool bRestartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmStartSession(out uint handle, int flags, string sessionKey);

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmRegisterResources(
        uint handle,
        uint fileCount,
        string[] fileNames,
        uint appCount,
        RM_UNIQUE_PROCESS[] applications,
        uint serviceCount,
        string[] serviceNames
    );

    [DllImport("rstrtmgr.dll")]
    private static extern int RmGetList(
        uint handle,
        out uint processInfoNeeded,
        ref uint processInfo,
        [In, Out] RM_PROCESS_INFO[] affectedApplications,
        ref uint rebootReasons
    );

    [DllImport("rstrtmgr.dll")]
    private static extern int RmEndSession(uint handle);

    public static RM_PROCESS_INFO[] GetLockingProcesses(string path)
    {
        uint handle;
        string key = Guid.NewGuid().ToString("N").Substring(0, CCH_RM_SESSION_KEY);
        int result = RmStartSession(out handle, 0, key);
        if (result != 0) throw new InvalidOperationException("RmStartSession failed: " + result);
        try
        {
            result = RmRegisterResources(handle, 1, new[] { path }, 0, null, 0, null);
            if (result != 0) throw new InvalidOperationException("RmRegisterResources failed: " + result);
            uint needed = 0;
            uint count = 0;
            uint reasons = 0;
            result = RmGetList(handle, out needed, ref count, null, ref reasons);
            if (result == 0) return new RM_PROCESS_INFO[0];
            if (result != ERROR_MORE_DATA) throw new InvalidOperationException("RmGetList failed: " + result);
            var processes = new RM_PROCESS_INFO[needed];
            count = needed;
            result = RmGetList(handle, out needed, ref count, processes, ref reasons);
            if (result != 0) throw new InvalidOperationException("RmGetList failed: " + result);
            if (count == processes.Length) return processes;
            Array.Resize(ref processes, (int)count);
            return processes;
        }
        finally
        {
            RmEndSession(handle);
        }
    }
}
"@

$resolved = (Resolve-Path -LiteralPath $Path).Path
[RestartManagerQuery]::GetLockingProcesses($resolved) |
    Select-Object @{Name='ProcessId';Expression={$_.Process.dwProcessId}}, strAppName, strServiceShortName, ApplicationType, AppStatus, TSSessionId, bRestartable
