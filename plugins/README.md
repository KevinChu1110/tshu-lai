# Plugins

一個 plugin = 一個 MCP server + `manifest.yaml`。規格：[spec/plugin-manifest.schema.json](../spec/plugin-manifest.schema.json)。

| plugin | 狀態 | 說明 |
| --- | --- | --- |
| [weather-tw](weather-tw/) | 可用 | 阿嬤家天氣，Open-Meteo |
| [calendar-tw](calendar-tw/) | 可用 | 農曆節日、節氣、初一十五 |
| [tv-taiwan](tv-taiwan/) | 可用 | 阿嬤的節目表（家人填），開播時切到看電視 scene |

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
