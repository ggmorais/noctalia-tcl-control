--!nonstrict
local function render(data)
  local s = data and data.state or {}
  barWidget.setGlyph("air-conditioning")
  barWidget.setText(data and data.ok and (s.powerSwitch == 1 and tostring(s.targetTemperature) .. "°" or "Off") or "—")
  barWidget.setTooltip(noctalia.tr("open_controls"))
end
noctalia.state.watch("status", render)
render(noctalia.state.get("status"))
function onClick() noctalia.togglePanel("ggmorais/tcl-control:controls") end
