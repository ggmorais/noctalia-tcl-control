--!nonstrict
local dataHome = noctalia.getenv("XDG_DATA_HOME") or noctalia.expandPath("~/.local/share")
local python = dataHome .. "/tcl-control/venv/bin/python"
local helper = noctalia.pluginDir() .. "/backend/backend.py"
local busy = false
local activeAction = nil
local isOpen = false
local draftTemperature = nil
local sentTemperature = nil
local temperatureDeadline = nil
local temperatureDebounceMs = 800
local last = noctalia.state.get("status") or { ok = false, error = noctalia.tr("connecting") }
local modeLabels = { noctalia.tr("auto"), noctalia.tr("cool"), noctalia.tr("dry"), noctalia.tr("fan"), noctalia.tr("heat") }
local modeValues = { "auto", "cool", "dry", "fan", "heat" }
local fanLabels = { noctalia.tr("auto"), noctalia.tr("low"), noctalia.tr("mid_low"), noctalia.tr("medium"), noctalia.tr("mid_high"), noctalia.tr("high") }
local fanValues = { "0", "2", "3", "4", "5", "6" }

local function targetTemperature()
  return draftTemperature or sentTemperature or (last.pending or {}).targetTemperature or (last.state or {}).targetTemperature
end

local function canEditTemperature()
  if not last.ok or type(targetTemperature()) ~= "number" then return false end
  if busy and activeAction ~= "temperature" then return false end
  for key in pairs(last.pending or {}) do
    if key ~= "targetTemperature" then return false end
  end
  return true
end

local function cancelTemperatureDraft()
  draftTemperature = nil
  sentTemperature = nil
  temperatureDeadline = nil
  panel.setNeedsFrameTick(false)
end

local function render()
  local s = last.state or {}
  local pending = last.pending and next(last.pending) ~= nil
  local enabled = last.ok == true and not busy and not pending and draftTemperature == nil and sentTemperature == nil
  local temperature = targetTemperature()
  local temperatureEnabled = canEditTemperature()
  local fanIndex = 0
  for i, value in ipairs(fanValues) do
    if tonumber(value) == s.windSpeed then fanIndex = i - 1 end
  end
  local status = last.error or noctalia.tr("connected")
  if last.ok then
    status = pending and noctalia.tr("pending") or (noctalia.tr("updated") .. " " .. os.date("%H:%M", last.fetched_at))
  end
  if busy then status = noctalia.tr("processing") end
  if sentTemperature and not busy then status = noctalia.tr("pending") end
  if draftTemperature then status = noctalia.tr("temperature_queued") end
  panel.render(ui.column({ gap = 16, flexGrow = 1 }, {
    ui.row({ gap = 8, align = "center" }, {
      ui.glyph({ name = "air-conditioning", size = 24, color = "primary" }),
      ui.label({ text = noctalia.tr("title"), fontSize = 18, fontWeight = "bold", flexGrow = 1 }),
      ui.button({ glyph = "refresh", onClick = "refresh", enabled = not busy, tooltip = noctalia.tr("refresh") }),
      ui.button({ glyph = "close", onClick = "closePanel" }),
    }),
    ui.row({ align = "center", gap = 12 }, {
      ui.label({ text = last.ok and (s.powerSwitch == 1 and noctalia.tr("on") or noctalia.tr("off")) or "—", flexGrow = 1 }),
      ui.toggle({ key = "power", checked = s.powerSwitch == 1, enabled = enabled, onChange = "power" }),
    }),
    ui.column({ gap = 8, padding = 16, radius = 12, fill = "surface_variant" }, {
      ui.label({ text = noctalia.tr("target_temperature"), color = "on_surface_variant" }),
      ui.row({ gap = 16, align = "center", justify = "space_between" }, {
        ui.button({ glyph = "minus", onClick = "cooler", enabled = temperatureEnabled and (temperature or 16) > 16 }),
        ui.label({ text = tostring(temperature or "—") .. " °C", fontSize = 36, fontWeight = "bold", color = "primary" }),
        ui.button({ glyph = "plus", onClick = "warmer", enabled = temperatureEnabled and (temperature or 30) < 30 }),
      }),
      ui.label({ text = noctalia.tr("room_temperature") .. ": " .. tostring(s.currentTemperature or "—") .. " °C", color = "on_surface_variant" }),
    }),
    ui.row({ gap = 12, align = "center" }, {
      ui.label({ text = noctalia.tr("mode"), width = 90 }),
      ui.select({ key = "mode", options = modeLabels, selectedIndex = s.workMode or 0, enabled = enabled, onChange = "mode", flexGrow = 1 }),
    }),
    ui.row({ gap = 12, align = "center" }, {
      ui.label({ text = noctalia.tr("fan_speed"), width = 90 }),
      ui.select({ key = "fan", options = fanLabels, selectedIndex = fanIndex, enabled = enabled, onChange = "fan", flexGrow = 1 }),
    }),
    ui.row({ gap = 12, align = "center" }, {
      ui.label({ text = noctalia.tr("screen"), flexGrow = 1 }),
      ui.toggle({ key = "screen", checked = s.screen == 1, enabled = enabled, onChange = "screen" }),
    }),
    ui.label({ text = status, color = last.ok and "on_surface_variant" or "error", maxLines = 2 }),
    ui.label({ text = noctalia.tr("cloud_notice"), fontSize = 12, color = "on_surface_variant" }),
  }))
end

local send
local flushTemperature

local function applyStatus(data)
  last = data
  if not data.ok then
    cancelTemperatureDraft()
  elseif sentTemperature and (data.state or {}).targetTemperature == sentTemperature
      and (data.pending or {}).targetTemperature == nil then
    sentTemperature = nil
  end
end

send = function(action, value)
  if busy then return end
  busy = true
  activeAction = action
  render()
  local accepted = noctalia.runAsync({ python, helper, action, value or "" }, function(result)
    busy = false
    activeAction = nil
    local data = noctalia.json.decode(result.stdout)
    if data then
      applyStatus(data)
      noctalia.state.set("status", data)
    else
      applyStatus({ ok = false, error = noctalia.tr("unavailable") })
    end
    -- Frame ticks stop when the panel closes. Finish an already chosen draft
    -- after an in-flight request, without losing the user's final selection.
    if not isOpen then flushTemperature(true) end
    render()
  end)
  if not accepted then
    busy = false
    activeAction = nil
    applyStatus({ ok = false, error = noctalia.tr("unavailable") })
    render()
  end
end

flushTemperature = function(force)
  if draftTemperature == nil or busy then return end
  if not force and noctalia.nowMs() < temperatureDeadline then return end
  local value = draftTemperature
  draftTemperature = nil
  temperatureDeadline = nil
  panel.setNeedsFrameTick(false)
  -- Clicking back to the current requested/reported value needs no cloud call.
  if value == targetTemperature() then render(); return end
  sentTemperature = value
  send("temperature", tostring(value))
end

local function stepTemperature(delta)
  if not canEditTemperature() then return end
  draftTemperature = math.min(30, math.max(16, targetTemperature() + delta))
  temperatureDeadline = noctalia.nowMs() + temperatureDebounceMs
  panel.setNeedsFrameTick(true)
  render()
end

noctalia.state.watch("status", function(data) applyStatus(data); render() end)
function onOpen() isOpen = true; render() end
function onClose()
  isOpen = false
  panel.setNeedsFrameTick(false)
  flushTemperature(true)
end
function onExit() cancelTemperatureDraft() end
function onFrameTick() flushTemperature(false) end
function closePanel() panel.close() end
function refresh() send("refresh") end
function power(value) send("power", value == "true" and "on" or "off") end
function screen(value) send("screen", value == "true" and "on" or "off") end
function cooler() stepTemperature(-1) end
function warmer() stepTemperature(1) end
function mode(index) send("mode", modeValues[(tonumber(index) or 0) + 1]) end
function fan(index) send("fan", fanValues[(tonumber(index) or 0) + 1]) end
