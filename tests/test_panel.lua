-- Exercise the actual panel script with fake Noctalia APIs, clock and cloud.
-- The panel intentionally uses the common Lua/Luau subset. No device commands.
local function status(target, pending)
  return {
    ok = true, state = { targetTemperature = target or 22, currentTemperature = 26,
      powerSwitch = 1, workMode = 1, windSpeed = 3, screen = 1 },
    pending = pending or {}, fetched_at = 1700000000,
  }
end

local function runtime(initial, rejectLaunch)
  local r = { now = 0, calls = {}, callbacks = {}, ticking = false }
  local env = setmetatable({}, { __index = _G })
  env.noctalia = {
    getenv = function() return nil end,
    expandPath = function(path) return path end,
    pluginDir = function() return "/plugin" end,
    tr = function(key) return key end,
    nowMs = function() return r.now end,
    json = { decode = function(data) return data end },
    state = {
      get = function() return initial or status() end,
      set = function(_, data) r.watch(data) end,
      watch = function(_, callback) r.watch = callback end,
    },
    runAsync = function(argv, callback)
      if rejectLaunch then return false end
      table.insert(r.calls, argv)
      table.insert(r.callbacks, callback)
      return true
    end,
  }
  env.panel = {
    render = function(tree) r.tree = tree end,
    setNeedsFrameTick = function(enabled) r.ticking = enabled end,
    close = function() env.onClose() end,
  }
  env.ui = setmetatable({}, { __index = function(_, kind)
    return function(props, children) return { kind = kind, props = props, children = children or {} } end
  end })
  assert(loadfile("tcl-control/panel.luau", "t", env))()
  r.env = env
  function r.advance(ms)
    r.now = r.now + ms
    if r.ticking then env.onFrameTick() end
  end
  function r.finish(data)
    local callback = table.remove(r.callbacks, 1)
    assert(callback, "No pending subprocess callback")
    callback({ stdout = data, exitCode = data.ok and 0 or 1 })
  end
  local function find(node, predicate)
    if predicate(node) then return node end
    for _, child in ipairs(node.children) do
      local result = find(child, predicate)
      if result then return result end
    end
  end
  function r.temperature()
    local label = find(r.tree, function(node) return node.kind == "label" and node.props.fontSize == 36 end)
    return label.props.text
  end
  function r.buttonEnabled(callback)
    return find(r.tree, function(node) return node.kind == "button" and node.props.onClick == callback end).props.enabled
  end
  env.onOpen()
  return r
end

local function equal(actual, expected)
  assert(actual == expected, "Expected " .. tostring(expected) .. ", got " .. tostring(actual))
end

local tests = {}

function tests.burst_sends_only_final_target()
  local r = runtime()
  r.env.warmer(); r.env.warmer(); r.env.warmer()
  equal(r.temperature(), "25 °C")
  equal(#r.calls, 0)
  r.advance(799); equal(#r.calls, 0)
  r.advance(1); equal(#r.calls, 1)
  equal(r.calls[1][3], "temperature"); equal(r.calls[1][4], "25")
  equal(r.temperature(), "25 °C")
  r.finish(status(22, { targetTemperature = 25 }))
  equal(r.temperature(), "25 °C")
  r.watch(status(25))
  equal(r.temperature(), "25 °C")
  equal(r.ticking, false)
end

function tests.delay_restarts_after_every_click()
  local r = runtime()
  r.env.warmer(); r.advance(600); r.env.warmer()
  r.advance(799); equal(#r.calls, 0)
  r.advance(1); equal(#r.calls, 1); equal(r.calls[1][4], "24")
end

function tests.returning_to_original_sends_nothing()
  local r = runtime()
  r.env.warmer(); r.env.cooler(); r.advance(800)
  equal(#r.calls, 0); equal(r.temperature(), "22 °C"); equal(r.ticking, false)
end

function tests.temperature_limits()
  local r = runtime()
  for _ = 1, 20 do r.env.warmer() end
  equal(r.temperature(), "30 °C"); equal(r.buttonEnabled("warmer"), false)
  r.advance(800); equal(r.calls[1][4], "30")
  r.finish(status(30))
  for _ = 1, 25 do r.env.cooler() end
  equal(r.temperature(), "16 °C"); equal(r.buttonEnabled("cooler"), false)
  r.advance(800); equal(r.calls[2][4], "16")
end

function tests.poll_does_not_overwrite_unsent_selection()
  local r = runtime()
  r.env.warmer(); r.env.warmer()
  r.watch(status(22))
  equal(r.temperature(), "24 °C")
  r.advance(800); equal(r.calls[1][4], "24")
end

function tests.clicks_during_request_queue_without_concurrent_sends()
  local r = runtime()
  r.env.warmer(); r.advance(800)
  equal(#r.calls, 1)
  r.env.warmer(); r.env.warmer(); r.advance(800)
  equal(#r.calls, 1); equal(r.temperature(), "25 °C")
  r.finish(status(22, { targetTemperature = 23 }))
  equal(r.temperature(), "25 °C")
  r.advance(0); equal(#r.calls, 2); equal(r.calls[2][4], "25")
end

function tests.new_target_does_not_wait_for_device_confirmation()
  local r = runtime(status(22, { targetTemperature = 24 }))
  r.env.warmer(); r.advance(800)
  equal(r.calls[1][4], "25")
end

function tests.error_cancels_draft_and_does_not_retry()
  local r = runtime()
  r.env.warmer(); r.watch({ ok = false, error = "offline" }); r.advance(2000)
  equal(#r.calls, 0); equal(r.ticking, false)
  r.watch(status(22)); r.advance(2000)
  equal(#r.calls, 0); equal(r.temperature(), "22 °C")
end

function tests.failed_send_cancels_newly_queued_draft()
  local r = runtime()
  r.env.warmer(); r.advance(800); r.env.warmer()
  r.finish({ ok = false, error = "offline" }); r.advance(2000)
  equal(#r.calls, 1); equal(r.ticking, false)
end

function tests.close_flushes_once()
  local r = runtime()
  r.env.warmer(); r.env.warmer(); r.env.onClose(); r.env.onClose()
  equal(#r.calls, 1); equal(r.calls[1][4], "24"); equal(r.ticking, false)
end

function tests.close_during_request_preserves_final_draft()
  local r = runtime()
  r.env.warmer(); r.advance(800); r.env.warmer(); r.env.onClose()
  equal(#r.calls, 1)
  r.finish(status(22, { targetTemperature = 23 }))
  equal(#r.calls, 2); equal(r.calls[2][4], "24")
end

function tests.exit_cancels_unsent_draft()
  local r = runtime()
  r.env.warmer(); r.env.onExit(); r.advance(1000)
  equal(#r.calls, 0); equal(r.ticking, false)
end

function tests.launch_failure_stops_timer()
  local r = runtime(nil, true)
  r.env.warmer(); r.advance(800)
  equal(r.ticking, false); equal(r.temperature(), "— °C")
end

function tests.unrelated_pending_command_blocks_temperature()
  local r = runtime(status(22, { workMode = 2 }))
  equal(r.buttonEnabled("warmer"), false)
  r.env.warmer(); r.advance(1000); equal(#r.calls, 0)
end

local count = 0
for name, test in pairs(tests) do
  test()
  count = count + 1
  print("PASS " .. name)
end
print(tostring(count) .. " panel debounce tests passed (no real commands sent).")
