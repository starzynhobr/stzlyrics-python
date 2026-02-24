local lyricsTable = {}
local currentTrackKey = ""
local hasActiveTrack = false
local searchInProgress = false
local pendingTrackKey = ""
local lastRequestedTrackKey = ""
local searchCounter = 0
local currentResultPath = ""
local lastResultPath = ""
local lastDisplayedLine = ""
local retryPending = false
local retryAt = 0
local retryAttempts = 0
local retryTrackKey = ""
local syncCurrentIndex = 1
local lastSyncPos = -1
local function Trim(str)
    return (str:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function NormalizeText(str)
    if not str then return "" end
    str = Trim(str)
    str = string.lower(str)
    str = str:gsub("%s+", " ")
    return str
end

local function IsMissingValue(str)
    if str == "" then return true end
    local lower = string.lower(str)
    return lower == "n/a"
end

local function GetTrackValues()
    local artist = SKIN:GetMeasure("mArtist")
    local title = SKIN:GetMeasure("mTitle")
    local a = artist and artist:GetStringValue() or ""
    local t = title and title:GetStringValue() or ""
    return Trim(a), Trim(t)
end

local function GetTrackKey()
    local a, t = GetTrackValues()
    return NormalizeText(a) .. " - " .. NormalizeText(t)
end

local function IsTrackActive()
    local a, t = GetTrackValues()
    return (not IsMissingValue(a)) and (not IsMissingValue(t))
end

local function SetMeterText(text, force)
    text = text or ""
    if not force and text == lastDisplayedLine then
        return
    end
    lastDisplayedLine = text
    SKIN:Bang("!SetOption", "MeterLyrics", "Text", text)
    SKIN:Bang("!UpdateMeter", "MeterLyrics")
    SKIN:Bang("!Redraw")
end

local function SafeRemoveFile(path)
    if not path or path == "" then return end
    os.remove(path)
end

local function JsonUnescape(str)
    if not str then return "" end
    str = str:gsub("\\\"", "\"")
    str = str:gsub("\\\\", "\\")
    str = str:gsub("\\/", "/")
    str = str:gsub("\\n", "\n")
    str = str:gsub("\\r", "\r")
    str = str:gsub("\\t", "\t")
    return str
end

local function ExtractJsonString(json, valueStart)
    local currentIdx = valueStart
    while true do
        local qStart, qEnd = string.find(json, '"', currentIdx, true)
        if not qStart then
            return nil, nil
        end

        local backslashCount = 0
        local i = qStart - 1
        while i >= valueStart do
            if string.sub(json, i, i) == "\\" then
                backslashCount = backslashCount + 1
                i = i - 1
            else
                break
            end
        end

        if backslashCount % 2 == 0 then
            local raw = string.sub(json, valueStart, qStart - 1)
            return raw, qStart + 1
        else
            currentIdx = qEnd + 1
        end
    end
end

local function FindJsonField(json, field, startIdx, endIdx)
    local key = '"' .. field .. '":"'
    local kStart, kEnd = string.find(json, key, startIdx, true)
    if not kStart then
        return nil, nil, nil
    end
    if endIdx and kStart > endIdx then
        return nil, nil, nil
    end

    local raw, nextIdx = ExtractJsonString(json, kEnd + 1)
    if not raw then
        return nil, nil, nil
    end

    if endIdx and nextIdx and nextIdx > (endIdx + 1) then
        return nil, nil, nil
    end

    return raw, nextIdx, kStart
end

local function NormalizeForMatch(str)
    str = NormalizeText(str)
    str = str:gsub("[^%w%s]", "")
    return str
end

local function IsLikelyMatch(a, b)
    if a == "" or b == "" then return false end
    if a == b then return true end
    if a:find(b, 1, true) or b:find(a, 1, true) then
        return true
    end
    return false
end

local function SelectLyrics(json, artistKey, titleKey)
    local searchIdx = 1

    while true do
        local trackRaw, nextIdx = FindJsonField(json, "trackName", searchIdx)
        if not trackRaw then
            break
        end

        local nextTrackStart = string.find(json, '"trackName":"', nextIdx, true)
        local rangeEnd = nextTrackStart and (nextTrackStart - 1) or #json

        local artistRaw = FindJsonField(json, "artistName", nextIdx, rangeEnd)
        local syncedRaw = FindJsonField(json, "syncedLyrics", nextIdx, rangeEnd)
        local plainRaw = FindJsonField(json, "plainLyrics", nextIdx, rangeEnd)

        local trackName = NormalizeForMatch(JsonUnescape(trackRaw))
        local artistName = NormalizeForMatch(JsonUnescape(artistRaw or ""))

        if IsLikelyMatch(artistName, artistKey) and IsLikelyMatch(trackName, titleKey) then
            if syncedRaw then
                return JsonUnescape(syncedRaw), true
            end
            if plainRaw then
                return JsonUnescape(plainRaw), false
            end
        end

        if nextTrackStart then
            searchIdx = nextTrackStart + 1
        else
            break
        end
    end

    local syncedRaw = FindJsonField(json, "syncedLyrics", 1)
    if syncedRaw then
        return JsonUnescape(syncedRaw), true
    end

    local plainRaw = FindJsonField(json, "plainLyrics", 1)
    if plainRaw then
        return JsonUnescape(plainRaw), false
    end

    return nil, false
end

local function StartSearch(force)
    if searchInProgress then return end
    if pendingTrackKey == "" then return end
    if not force and pendingTrackKey == lastRequestedTrackKey then return end

    currentTrackKey = pendingTrackKey
    lastRequestedTrackKey = pendingTrackKey
    lyricsTable = {}
    syncCurrentIndex = 1
    lastSyncPos = -1
    lastDisplayedLine = ""
    searchInProgress = true
    searchCounter = searchCounter + 1

    local fileName = "lyrics_result_" .. searchCounter .. ".json"
    currentResultPath = SKIN:GetVariable("CURRENTPATH") .. fileName

    if lastResultPath ~= "" and lastResultPath ~= currentResultPath then
        SafeRemoveFile(lastResultPath)
    end
    lastResultPath = currentResultPath

    SKIN:Bang("!SetVariable", "SearchResultFile", fileName)
    local url = "https://lrclib.net/api/search?artist_name=" .. EncodeMeasure("mArtist") .. "&track_name=" .. EncodeMeasure("mTitle")
    local param = string.format('-s --connect-timeout 5 --max-time 12 --retry 2 --retry-delay 1 -o "%s" "%s"', currentResultPath, url)
    SKIN:Bang("!SetOption", "mSearchCmd", "Parameter", param)
    SKIN:Bang("!UpdateMeasure", "mSearchCmd")
    SetMeterText("Loading...", true)
    SKIN:Bang("!CommandMeasure", "mSearchCmd", "Run")
end

local function TryStartPending()
    if pendingTrackKey ~= "" and pendingTrackKey ~= lastRequestedTrackKey then
        StartSearch(false)
    end
end

local function ScheduleRetry()
    if retryAttempts >= 1 then return false end
    retryAttempts = retryAttempts + 1
    retryPending = true
    retryAt = os.time() + 1
    retryTrackKey = lastRequestedTrackKey
    SetMeterText("Tentando novamente...", true)
    return true
end

function TickRetry()
    if not retryPending then return end
    if searchInProgress then return end
    if retryTrackKey == "" or retryTrackKey ~= lastRequestedTrackKey then
        retryPending = false
        return
    end
    if os.time() < retryAt then return end
    retryPending = false
    StartSearch(true)
end

function HandleTrackChange()
    if not IsTrackActive() then
        hasActiveTrack = false
        currentTrackKey = ""
        pendingTrackKey = ""
        lyricsTable = {}
        syncCurrentIndex = 1
        lastSyncPos = -1
        lastDisplayedLine = ""
        SetMeterText("", true)
        SKIN:Bang("!HideMeter", "MeterLyrics")
        SKIN:Bang("!UpdateMeter", "MeterLyrics")
        SKIN:Bang("!Redraw")
        return
    end

    hasActiveTrack = true
    pendingTrackKey = GetTrackKey()
    retryAttempts = 0
    retryPending = false
    retryTrackKey = pendingTrackKey
    SKIN:Bang("!ShowMeter", "MeterLyrics")
    StartSearch(false)
end

function ForceSearch()
    if not IsTrackActive() then return end
    pendingTrackKey = GetTrackKey()
    retryAttempts = 0
    retryPending = false
    retryTrackKey = pendingTrackKey
    StartSearch(true)
end

function Initialize()
    -- Nothing
end

function EncodeMeasure(measureName)
    local measure = SKIN:GetMeasure(measureName)
    if not measure then return "" end
    local str = measure:GetStringValue()
    if not str then return "" end

    if str then
        str = string.gsub (str, "\n", "\r\n")
        str = string.gsub (str, "([^%w %-%_%.%~])",
            function (c) return string.format ("%%%02X", string.byte(c)) end)
        str = string.gsub (str, " ", "+")
    end
    return str
end

function ReadFile(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local content = f:read("*all")
    f:close()
    return content
end

function ParseTime(timeStr)
    local m, s = timeStr:match("(%d+):(%d+%.?%d*)")
    if not m or not s then return 0 end
    return (tonumber(m) * 60) + tonumber(s)
end

function ProcessLyrics()
    searchInProgress = false

    if not hasActiveTrack then
        return
    end

    local liveTrackKey = GetTrackKey()
    if lastRequestedTrackKey == "" or liveTrackKey ~= lastRequestedTrackKey then
        SafeRemoveFile(currentResultPath)
        TryStartPending()
        return
    end
    local json = ReadFile(currentResultPath)
    lyricsTable = {}
    syncCurrentIndex = 1
    lastSyncPos = -1
    if not json or json == "" then
        if ScheduleRetry() then
            SafeRemoveFile(currentResultPath)
            return
        end
        SetMeterText("Erro ao ler arquivo", true)
        SafeRemoveFile(currentResultPath)
        TryStartPending()
        return
    end

    local artist, title = GetTrackValues()
    local artistKey = NormalizeForMatch(artist)
    local titleKey = NormalizeForMatch(title)

    local rawLyrics, isSynced = SelectLyrics(json, artistKey, titleKey)
    if not rawLyrics or rawLyrics == "" then
        SetMeterText("Letra não encontrada", true)
        SafeRemoveFile(currentResultPath)
        TryStartPending()
        return
    end

    if isSynced then
        for line in rawLyrics:gmatch("[^\r\n]+") do
            local tStr, text = line:match("%[(%d+:%d+%.?%d*)%](.*)")
            if tStr then
                local t = ParseTime(tStr)
                table.insert(lyricsTable, {time = t, text = text})
            end
        end
    end
    if #lyricsTable == 0 then
        local firstLine = rawLyrics:match("([^\r\n]+)") or rawLyrics
        SetMeterText(firstLine, true)
    else
        SetMeterText("Sincronizando...", true)
        SyncLyrics()
    end

    SafeRemoveFile(currentResultPath)
    TryStartPending()
end

function SyncLyrics()
    if #lyricsTable == 0 then return end

    local measurePos = SKIN:GetMeasure("mPosition")
    if not measurePos then return end

    local currentPos = tonumber(measurePos:GetValue())
    local posStr = measurePos:GetStringValue() or ""
    if posStr:find(":") then
        currentPos = ParseTime(posStr)
    elseif not currentPos then
        currentPos = tonumber(posStr) or 0
    end
    currentPos = currentPos or 0
    local offset = tonumber(SKIN:GetVariable("LyricsOffset", "0")) or 0
    currentPos = currentPos + offset
    if currentPos < 0 then currentPos = 0 end

    local total = #lyricsTable
    local currentIndex = syncCurrentIndex
    if currentIndex < 1 or currentIndex > total then
        currentIndex = 1
    end

    if lastSyncPos >= 0 and currentPos + 0.05 < lastSyncPos then
        currentIndex = 1
    end

    while currentIndex < total and currentPos >= lyricsTable[currentIndex + 1].time do
        currentIndex = currentIndex + 1
    end

    while currentIndex > 1 and currentPos < lyricsTable[currentIndex].time do
        currentIndex = currentIndex - 1
    end

    syncCurrentIndex = currentIndex
    lastSyncPos = currentPos
    local line = lyricsTable[currentIndex]
    local displayStr = (line and line.text) or ""
    SetMeterText(displayStr, false)
end




