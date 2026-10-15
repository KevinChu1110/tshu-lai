# Plugins

一個 plugin = 一個 MCP server + `manifest.yaml`。規格：[spec/plugin-manifest.schema.json](../spec/plugin-manifest.schema.json)。

| plugin | 狀態 | 說明 |
| --- | --- | --- |
| [weather-tw](weather-tw/) | 可用 | 阿嬤家天氣，Open-Meteo |
| [examples/tv-taiwan](examples/tv-taiwan/) | 只有 manifest | 節目表與八點檔劇情，等社群接資料來源 |

## 約定的 tool

- `topics`：回傳今天的話題，每行一個。knowledge plugin 實作。
- `poll_events`：回傳待觸發事件名，每行一個。trigger plugin 實作，引擎每分鐘問。
- 其他 tool 列在 `provides.tools`，對話腦需要時呼叫。

## 啟用

`data/config.yaml`：

```yaml
plugins:
  enabled: [weather-tw]
```

人格卡 `home` 的座標會以 `TSHULAI_HOME_LAT` / `TSHULAI_HOME_LNG` 傳給 plugin。
