--!nonstrict
local function render(data)
  local s = data and data.state or {}
  local on = data and data.ok and s.powerSwitch == 1
  shortcut.setLabel(on and (noctalia.tr("short_title") .. " · " .. tostring(s.targetTemperature or "—") .. "°") or noctalia.tr("short_title"))
  shortcut.setIcon("air-conditioning")
  shortcut.setActive(on == true)
end
noctalia.state.watch("status", render)
render(noctalia.state.get("status"))
function onClick() noctalia.togglePanel("ggmorais/tcl-control:controls") end
function onRightClick() noctalia.togglePanel("ggmorais/tcl-control:controls") end
