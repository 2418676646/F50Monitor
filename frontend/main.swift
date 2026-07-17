import Cocoa
import SwiftUI

struct StatusData: Codable {
    var temperature: Double
    var tx_throughput: Int64
    var rx_throughput: Int64
    var wan_ip: String
    var lte_rsrp: Int
    var z5g_rsrp: Int?
    var version: String
    var network_type: String
    var provider: String?
    var uptime: Int64?
    var data_usage: Int64?
}

class AppDelegate: NSObject, NSApplicationDelegate, ObservableObject {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var timer: Timer?
    @Published var currentData: StatusData?

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.action = #selector(togglePopover(_:))
            updateButtonOffline()
        }
        
        let contentView = ContentView(appDelegate: self)
        popover = NSPopover()
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(rootView: contentView)
        
        startFetching()
    }
    
    func startFetching() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.fetchData()
        }
        fetchData()
    }
    
    func fetchData() {
        guard let url = URL(string: "http://192.168.0.1:55050/api/status") else { return }
        let task = URLSession.shared.dataTask(with: url) { data, response, error in
            guard let data = data, error == nil else {
                DispatchQueue.main.async {
                    self.currentData = nil
                    self.updateButtonOffline()
                }
                return
            }
            do {
                let status = try JSONDecoder().decode(StatusData.self, from: data)
                DispatchQueue.main.async {
                    self.currentData = status
                    self.updateButton(temp: status.temperature, tx: status.tx_throughput, rx: status.rx_throughput)
                }
            } catch {
                DispatchQueue.main.async {
                    self.currentData = nil
                    self.updateButtonOffline()
                }
            }
        }
        task.resume()
    }
    
    func updateButtonOffline() {
        DispatchQueue.main.async {
            self.statusItem.button?.image = nil
            self.statusItem.button?.title = "等待获取数据..."
            
            // Set font to match standard menu bar font
            let font = NSFont.menuBarFont(ofSize: 12)
            let attrs: [NSAttributedString.Key: Any] = [.font: font]
            let attrStr = NSAttributedString(string: " 等待连接...", attributes: attrs)
            self.statusItem.button?.attributedTitle = attrStr
        }
    }
    
    func updateButton(temp: Double, tx: Int64, rx: Int64) {
        // Clear text title so we only draw the image
        self.statusItem.button?.title = ""
        self.statusItem.button?.attributedTitle = NSAttributedString(string: "")
        
        func formatSpeed(_ bytesPerSec: Int64) -> String {
            let kb = Double(bytesPerSec) / 1024.0
            if kb < 1000 {
                return String(format: "%5.1f K", kb) // Pad to 5 chars (e.g. " 12.5 K", "999.0 K")
            }
            return String(format: "%5.1f M", kb / 1024.0)
        }
        
        let tempStr = temp > 0 ? String(format: "%.1f°", temp) : "--.-°"
        let txStr = formatSpeed(tx)
        let rxStr = formatSpeed(rx)
        
        // Use monospaced digits so the numbers look highly professional and aligned
        let fontTemp = NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .medium)
        let fontSpeed = NSFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
        let fontArrow = NSFont.systemFont(ofSize: 8, weight: .bold)
        
        let totalWidth: CGFloat = 88.0
        
        let image = NSImage(size: NSSize(width: totalWidth, height: 18))
        image.lockFocus()
        
        // 1. Draw Temperature (Left aligned)
        let tempAttrs: [NSAttributedString.Key: Any] = [.font: fontTemp]
        tempStr.draw(at: NSPoint(x: 2, y: 2), withAttributes: tempAttrs)
        
        // 2. Draw Subtle Vertical Separator "|"
        NSColor.tertiaryLabelColor.set()
        let path = NSBezierPath()
        path.move(to: NSPoint(x: 38, y: 3))
        path.line(to: NSPoint(x: 38, y: 15))
        path.lineWidth = 1.0
        path.stroke()
        
        // 3. Draw Speeds (Right aligned block)
        let speedX: CGFloat = 43.0
        let arrowAttrs: [NSAttributedString.Key: Any] = [.font: fontArrow, .foregroundColor: NSColor.secondaryLabelColor]
        let speedAttrs: [NSAttributedString.Key: Any] = [.font: fontSpeed]
        
        // Draw Up Arrow & Upload Speed
        "↑".draw(at: NSPoint(x: speedX, y: 9.5), withAttributes: arrowAttrs)
        txStr.draw(at: NSPoint(x: speedX + 8, y: 9), withAttributes: speedAttrs)
        
        // Draw Down Arrow & Download Speed
        "↓".draw(at: NSPoint(x: speedX, y: 0.5), withAttributes: arrowAttrs)
        rxStr.draw(at: NSPoint(x: speedX + 8, y: 0), withAttributes: speedAttrs)
        
        image.unlockFocus()
        image.isTemplate = true
        
        statusItem.button?.image = image
    }
    
    @objc func togglePopover(_ sender: AnyObject?) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            if let button = statusItem.button {
                // Need to activate the app to show the popover properly
                NSApp.activate(ignoringOtherApps: true)
                popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            }
        }
    }
    
    func quit() {
        NSApplication.shared.terminate(self)
    }
}

struct ContentView: View {
    @ObservedObject var appDelegate: AppDelegate
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Text("F50 设备详情")
                    .font(.system(size: 14, weight: .bold))
                
                Circle()
                    .fill(appDelegate.currentData != nil ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)
                    
                Spacer()
                
                Menu {
                    Button("退出 F50 状态栏") {
                        appDelegate.quit()
                    }
                } label: {
                    Image(systemName: "gearshape")
                        .foregroundColor(.secondary)
                }
                .menuStyle(.borderlessButton)
                .menuIndicator(.hidden)
                .frame(width: 16, height: 16)
            }
            Divider()
            
            if let data = appDelegate.currentData {
                VStack(spacing: 8) {
                    
                    let prov = data.provider?.isEmpty == false ? data.provider! : "未知"
                    InfoRow(label: "运营商", value: prov)
                    
                    let netTypeStr = data.network_type == "ENDC" ? "LTE (NR_NSA)" : data.network_type
                    InfoRow(label: "网络类型", value: netTypeStr)
                    
                    InfoRow(label: "WAN IP", value: data.wan_ip.isEmpty ? "未获取" : data.wan_ip)
                    
                    let signalLabel = data.network_type == "ENDC" ? "5G NR" : "LTE"
                    let rsrpVal = (data.z5g_rsrp != nil && data.z5g_rsrp! < 0) ? data.z5g_rsrp! : data.lte_rsrp
                    let signalQual = rsrpVal > -85 ? "优秀" : (rsrpVal > -105 ? "良好" : "较差")
                    InfoRow(label: "信号强度", value: "\(rsrpVal) dBm（\(signalLabel)，\(signalQual)）")
                    
                    InfoRow(label: "设备温度", value: String(format: "%.1f °C", data.temperature))
                    
                    if let up = data.uptime {
                        let d = up / 86400
                        let h = (up % 86400) / 3600
                        let m = (up % 3600) / 60
                        let upStr = "\(d)天\(h)小时\(m)分钟"
                        InfoRow(label: "运行时长", value: upStr)
                    }
                    
                    if let usage = data.data_usage {
                        let gb = Double(usage) / 1024.0 / 1024.0 / 1024.0
                        InfoRow(label: "已用流量", value: String(format: "%.2f GB (自开机起)", gb))
                    }
                }
            } else {
                Text("等待数据连接中...")
                    .foregroundColor(.gray)
                    .frame(height: 80)
            }
        }
        .padding(16)
        .frame(width: 250)
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    var body: some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value).fontWeight(.medium)
        }
    }
}

// Run the app as an accessory (doesn't show in dock)
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
