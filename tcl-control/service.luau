--!nonstrict
local dataHome = noctalia.getenv("XDG_DATA_HOME") or noctalia.expandPath("~/.local/share")
local python = dataHome .. "/tcl-control/venv/bin/python"
local helper = noctalia.pluginDir() .. "/backend/backend.py"
local function quote(value) return "'" .. string.gsub(value, "'", "'\\''") .. "'" end

if not noctalia.fileExists(python) then
  noctalia.state.set("status", { ok = false, error = noctalia.tr("setup_required") })
else
  noctalia.state.set("status", { ok = false, error = noctalia.tr("connecting") })
  local started = noctalia.runStream(quote(python) .. " " .. quote(helper) .. " serve", function(line)
    local data = noctalia.json.decode(line)
    if data then noctalia.state.set("status", data) end
  end)
  if not started then
    noctalia.state.set("status", { ok = false, error = noctalia.tr("start_failed") })
  end
end
