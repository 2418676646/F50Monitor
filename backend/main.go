package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

type F50Status struct {
	Temperature float64 `json:"temperature"`
	TxThroughput int64  `json:"tx_throughput"`
	RxThroughput int64  `json:"rx_throughput"`
	WanIP       string  `json:"wan_ip"`
	LteRsrp     int     `json:"lte_rsrp"`
	Z5gRsrp     int     `json:"z5g_rsrp"`
	Version     string  `json:"version"`
	NetworkType string  `json:"network_type"`
	Provider    string  `json:"provider,omitempty"`
	Uptime      int64   `json:"uptime,omitempty"`
	DataUsage   int64   `json:"data_usage,omitempty"`
}

var (
	currentStatus F50Status
	statusMutex   sync.RWMutex
	lastRxBytes   int64
	lastTxBytes   int64
	lastNetTime   time.Time
)

func getTemperature() float64 {
	for i := 0; i < 30; i++ {
		typeBytes, err := os.ReadFile(fmt.Sprintf("/sys/class/thermal/thermal_zone%d/type", i))
		if err != nil {
			continue
		}
		typeName := strings.TrimSpace(string(typeBytes))
		if typeName == "apcpu0-thmzone" || typeName == "soc-thmzone" || typeName == "board-thmzone" {
			tempBytes, err := os.ReadFile(fmt.Sprintf("/sys/class/thermal/thermal_zone%d/temp", i))
			if err == nil {
				if tempVal, err := strconv.ParseFloat(strings.TrimSpace(string(tempBytes)), 64); err == nil {
					return tempVal / 1000.0
				}
			}
		}
	}
	
	for i := 0; i < 30; i++ {
		tempBytes, err := os.ReadFile(fmt.Sprintf("/sys/class/thermal/thermal_zone%d/temp", i))
		if err == nil {
			if tempVal, err := strconv.ParseFloat(strings.TrimSpace(string(tempBytes)), 64); err == nil {
				if tempVal > 1000 && tempVal < 100000 {
					return tempVal / 1000.0
				}
				if tempVal > 0 && tempVal < 100 {
					return tempVal
				}
			}
		}
	}
	return 0.0
}

func parseNetDev() (rx int64, tx int64) {
	data, err := os.ReadFile("/proc/net/dev")
	if err != nil {
		return 0, 0
	}
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.Contains(line, "sipa_eth0") || strings.Contains(line, "rmnet_data") {
			line = strings.ReplaceAll(line, ":", " ")
			parts := strings.Fields(line)
			if len(parts) >= 10 {
				r, _ := strconv.ParseInt(parts[1], 10, 64)
				t, _ := strconv.ParseInt(parts[9], 10, 64)
				rx += r
				tx += t
			}
		}
	}
	return
}

func getCarrier() string {
	cmd := exec.Command("getprop", "gsm.operator.alpha")
	output, err := cmd.Output()
	if err != nil {
		return "未知运营商"
	}
	operator := strings.TrimSpace(string(output))
	if operator == "" {
		cmd = exec.Command("getprop", "gsm.sim.operator.alpha")
		output, err = cmd.Output()
		if err == nil {
			operator = strings.TrimSpace(string(output))
		}
	}
	if operator == "" {
		return "未知运营商"
	}
	parts := strings.Split(operator, ",")
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			return p
		}
	}
	return "未知运营商"
}

func getNetworkType() string {
	cmd := exec.Command("dumpsys", "telephony.registry")
	output, err := cmd.Output()
	if err == nil {
		outStr := string(output)
		re := regexp.MustCompile(`TelephonyDisplayInfo\s*\{network=([^,]+),\s*override=([^}]+)\}`)
		match := re.FindStringSubmatch(outStr)
		if len(match) >= 3 {
			network := strings.TrimSpace(match[1])
			override := strings.TrimSpace(match[2])
			if override != "NONE" && override != "Unknown" && override != "" {
				return fmt.Sprintf("%s (%s)", network, override)
			}
			return network
		}
	}

	cmd = exec.Command("getprop", "gsm.network.type")
	output, err = cmd.Output()
	if err == nil {
		netType := strings.TrimSpace(string(output))
		if netType != "" {
			parts := strings.Split(netType, ",")
			for _, p := range parts {
				p = strings.TrimSpace(p)
				if p != "" && p != "Unknown" {
					return p
				}
			}
		}
	}
	return "未知网络"
}

func getSignalStrength() (int, int, string) {
	cmd := exec.Command("dumpsys", "telephony.registry")
	output, err := cmd.Output()
	if err != nil {
		return 0, 0, ""
	}
	outStr := string(output)

	var rsrpLTE = 0
	var rsrp5G = 0
	var sigType = ""

	matchNR := regexp.MustCompile(`ssRsrp\s*=\s*(-?\d+)`).FindStringSubmatch(outStr)
	if len(matchNR) >= 2 {
		if val, err := strconv.Atoi(matchNR[1]); err == nil && val != 2147483647 && val < 0 {
			rsrp5G = val
			sigType = "5G NR"
		}
	}
	
	matchLTE := regexp.MustCompile(`CellSignalStrengthLte:\s*rssi=(-?\d+)\s*rsrp=(-?\d+)`).FindStringSubmatch(outStr)
	if len(matchLTE) >= 3 {
		if val, err := strconv.Atoi(matchLTE[2]); err == nil && val != 2147483647 && val < 0 {
			rsrpLTE = val
			if sigType == "" {
				sigType = "4G LTE"
			}
		}
	}
	
	return rsrpLTE, rsrp5G, sigType
}

func getWanIP() string {
	ifaces, err := net.Interfaces()
	if err == nil {
		for _, iface := range ifaces {
			if strings.Contains(iface.Name, "sipa_eth") || strings.Contains(iface.Name, "rmnet") {
				addrs, err := iface.Addrs()
				if err == nil {
					for _, addr := range addrs {
						ipNet, ok := addr.(*net.IPNet)
						if ok && !ipNet.IP.IsLoopback() && ipNet.IP.To4() != nil {
							return ipNet.IP.String()
						}
					}
				}
			}
		}
	}
	return "未获取"
}

func getUptime() int64 {
	data, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return 0
	}
	parts := strings.Fields(string(data))
	if len(parts) > 0 {
		if val, err := strconv.ParseFloat(parts[0], 64); err == nil {
			return int64(val)
		}
	}
	return 0
}

func updateLoop() {
	lastNetTime = time.Now()
	lastRxBytes, lastTxBytes = parseNetDev()
	
	var loopCounter int = 0
	var cachedCarrier, cachedNetType, cachedWanIP string
	var cachedRsrpLTE, cachedRsrp5G int

	for {
		time.Sleep(1 * time.Second)
		loopCounter++
		
		// Fast operations: temp, net usage, uptime
		temp := getTemperature()
		uptime := getUptime()
		
		now := time.Now()
		rx, tx := parseNetDev()
		
		dt := now.Sub(lastNetTime).Seconds()
		var rxSpeed, txSpeed int64
		if dt > 0 {
			if rx >= lastRxBytes {
				rxSpeed = int64(float64(rx-lastRxBytes) / dt)
			}
			if tx >= lastTxBytes {
				txSpeed = int64(float64(tx-lastTxBytes) / dt)
			}
		}
		
		lastRxBytes = rx
		lastTxBytes = tx
		lastNetTime = now
		
		// Heavy operations (dumpsys/getprop): only run every 5 seconds to save F50 CPU & Battery
		if loopCounter == 1 || loopCounter % 5 == 0 {
			cachedCarrier = getCarrier()
			cachedNetType = getNetworkType()
			cachedRsrpLTE, cachedRsrp5G, _ = getSignalStrength()
		}
		
		// WAN IP is even heavier (network interfaces parsing)
		// If we haven't obtained a valid IP, check every 10 seconds.
		// If we already have it, it rarely changes (unless disconnected), so only verify every 5 minutes (300 seconds).
		var wanIpInterval = 300
		if cachedWanIP == "" || cachedWanIP == "未获取" {
			wanIpInterval = 10
		}
		if loopCounter == 1 || loopCounter % wanIpInterval == 0 {
			cachedWanIP = getWanIP()
		}

		statusMutex.Lock()
		currentStatus.Temperature = temp
		currentStatus.RxThroughput = rxSpeed
		currentStatus.TxThroughput = txSpeed
		currentStatus.DataUsage = rx + tx
		currentStatus.LteRsrp = cachedRsrpLTE
		currentStatus.Z5gRsrp = cachedRsrp5G
		currentStatus.NetworkType = cachedNetType
		currentStatus.Provider = cachedCarrier
		if cachedWanIP != "" {
			currentStatus.WanIP = cachedWanIP
		}
		currentStatus.Uptime = uptime
		currentStatus.Version = "Native Magisk"
		statusMutex.Unlock()
	}
}

func handler(w http.ResponseWriter, r *http.Request) {
	statusMutex.RLock()
	defer statusMutex.RUnlock()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(currentStatus)
}

func main() {
	go updateLoop()
	http.HandleFunc("/api/status", handler)
	fmt.Println("F50 Magisk Monitor running on 0.0.0.0:55050")
	log.Fatal(http.ListenAndServe("0.0.0.0:55050", nil))
}
