// Load service worker if supported
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/serviceworker.js');
    });
}

// initialize the map
var map = L.map('map', {
    renderer: L.canvas(),
    maxZoom: 20,
});

map.setView([-27.5, 133], 5);

// load a vector tile layer (CARTO Voyager) via MapLibre GL, keeping the same look as the previous raster layer
L.maplibreGL({
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
}).addTo(map);

// get url parameters
var urlParams = new URLSearchParams(window.location.search);
var default_suburb = null;
var default_state = null;
var default_commit = "latest";
var combined_info = null;
// null means every postcode in the loaded suburb, including addresses with no postcode.
var active_postcode = null;
var loaded_collection = null;
var loaded_state_file = null;
var applied_postcode = undefined;
var load_serial = 0;
if (urlParams.has("suburb") && urlParams.has("state")) {
    default_suburb = urlParams.get("suburb");
    default_state = urlParams.get("state");
    updateSiteDetails(default_suburb, default_state);
}
if (urlParams.has("commit")) {
    default_commit = urlParams.get("commit");
    default_commit = default_commit == "main" ? "latest" : default_commit;
}
if (urlParams.has("postcode") && urlParams.get("postcode")) {
    active_postcode = urlParams.get("postcode");
}

if (window.matchMedia('(display-mode: standalone)').matches) {
    gtag('event', 'PWA');
}

function updateSiteDetails(suburb, state) {
    formattedSuburb = suburb.replace("-", " ").replace(/(^\w|\s\w)/g, m => m.toUpperCase());
    newTitle = "NBN Technology Map - " + formattedSuburb;
    if (document.title != newTitle) {
        document.title = newTitle;
    }
    newDescription = "Map of NBN technology types in " + formattedSuburb + " " + state.toUpperCase() + ".";
    $('meta[name="description"]').attr("content", newDescription);
}

function updateSiteDetailed(suburb, state, data) {
    var features = (data && data.features) ? data.features : [];
    techBreakdown = features.reduce((acc, feature) => {
        if (!feature || !feature.properties || feature.properties.tech == null) {
            return acc;
        }
        if (feature.properties.tech in acc) {
            acc[feature.properties.tech] += 1;
        } else if (feature.properties.tech != "NULL") {
            acc[feature.properties.tech] = 1;
        }
        return acc;
    }, {});
    formattedSuburb = suburb.replace("-", " ").replace(/(^\w|\s\w)/g, m => m.toUpperCase());
    if (Object.keys(techBreakdown).length === 0 || !data || typeof data.generated !== "string") {
        newDescription = "Map of NBN technology types in " + formattedSuburb + " " + state.toUpperCase() + ".";
        $('meta[name="description"]').attr("content", newDescription);
        return;
    }
    primaryTech = Object.keys(techBreakdown).reduce((a, b) => techBreakdown[a] > techBreakdown[b] ? a : b);
    newDescription = "Map of NBN technology types in " + formattedSuburb + " " + state.toUpperCase() + " as of " + data.generated.split("T")[0] + ".";
    newDescription += " The primary technology is " + primaryTech + " with " + techBreakdown[primaryTech] + " premises, other technologies include " + Object.keys(techBreakdown).filter(tech => tech != primaryTech).map(tech => tech + " (" + techBreakdown[tech] + ")").join(", ") + ".";
    $('meta[name="description"]').attr("content", newDescription);
}

function addControlWithHTML(className, html) {
    // Add/replace a topright control with given className and innerHTML
    var dropdown = L.control({ position: 'topright' });
    dropdown.onAdd = function (map) {
        var div = L.DomUtil.create('div', className);
        div.innerHTML = html;
        return div;
    }
    if (document.getElementsByClassName(className).length > 0) {
        document.getElementsByClassName(className)[0].remove();
    }
    dropdown.addTo(map);
}

function format_suburb_data(data, term) {
    let formatted_data = [];
    for (var state in data) {
        let state_data = {text: state, children: []};
        for (var suburb of data[state]) {
            if (term != null && suburb.name.toLowerCase().indexOf(term.toLowerCase()) == -1) {
                continue;
            }
            state_data.children.push({id: state + "/" + suburb.name.toLowerCase().replace(/ /g, "-"), text: suburb.name });
        }
        if (state_data.children.length > 0) {
            formatted_data.push(state_data);
        }
    }
    return {results: formatted_data};
}

// download combined suburb data if not in cache
const cacheKey = 'suburb-cache';
const flatVal = localStorage.getItem(cacheKey) ?? '';
const [query, strVal, dateStr] = flatVal.split('|');
if (!query || !strVal || !dateStr) {
    fetch("https://cdn.jsdelivr.net/gh/LukePrior/nbn-upgrade-map@latest/results/combined-suburbs.json").then(res => res.json()).then(data => {
        const cacheVal = `${cacheKey}|${JSON.stringify(data)}|${(new Date()).toISOString()}`;
        localStorage.setItem(cacheKey, cacheVal);
    });
}

addControlWithHTML('suburb-selector-container', '<select id="suburb" class="suburb-selector" onchange="loadSuburb(this.value, default_commit)" style="width: 300px;"><option></option></select>');
$(document).ready(function() {
    $('.suburb-selector').select2({
        placeholder: "Select a suburb",
        allowClear: true,
        minimumInputLength: 3,
        ajax: {
            url: "https://cdn.jsdelivr.net/gh/LukePrior/nbn-upgrade-map@latest/results/combined-suburbs.json",
            dataType: 'json',
            delay: 10,
            transport: function(params, success, failure) {
                const cacheKey = 'suburb-cache';
                const flatVal = localStorage.getItem(cacheKey) ?? '';
                const [query, strVal, dateStr] = flatVal.split('|');
                if (query && strVal && dateStr) {
                    const date = new Date(dateStr);
                    const expireDate = Date.now() - 24*1000*60*60;
                    if (date?.getMonth && date > expireDate) {
                        const value = JSON.parse(strVal);
                        if (value) success(format_suburb_data(value, params.data.term));
                        return;
                    }
                    localStorage.removeItem(cacheKey); // remove expired
                }
                const request = $.ajax(params);
                request.then(function(data) {
                    const cacheVal = `${cacheKey}|${JSON.stringify(data)}|${(new Date()).toISOString()}`;
                    localStorage.setItem(cacheKey, cacheVal);
                    success(format_suburb_data(data, params.data.term));
                });
                request.fail(failure);
                return request;
            }
        }
    });
    if (default_suburb != null && default_state != null) {
        var option = new Option(default_suburb.replace("-", " ").replace(/(^\w|\s\w)/g, m => m.toUpperCase()), default_state + "/" + default_suburb, true, true);
        $('.suburb-selector').append(option).trigger('change');
    }
});

const dotTypes = {
    FTTP: {
        label: 'FTTP',
        colour: '#1D7044'
    },
    FTTPUpgrade: {
        label: 'FTTP Upgrade',
        colour: '#75AD6F'
    },
    FTTPUpgradeSoon: {
        label: 'FTTP Upgrade Soon',
        colour: '#C8E3C5'
    },
    OtherUpgrade: {
        label: 'Other Upgrade',
        colour: '#4464AD'
    },
    OtherUpgradeSoon: {
        label: 'Other Upgrade Soon',
        colour: '#44C5E3'
    },
    HFC: {
        label: 'HFC',
        colour: '#FFBE00',
    },
    FTTC: {
        label: 'FTTC',
        colour: '#FF7E01'
    },
    FTTN_FTTB: {
        label: 'FTTN/FTTB',
        colour: '#E3071D'
    },
    WirelessSat: {
        label: 'FW/SAT',
        colour: '#C91414'
    },
    Unknown: {
        label: 'Unknown',
        colour: '#888888'
    },
};

// add link to github repo in bottom left
var github = L.control({ position: 'bottomleft' });
github.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'info');
    div.style.backgroundColor = "#ffffff";
    div.style.opacity = "0.8";
    div.style.padding = "5px";
    div.style.borderRadius = "5px";
    div.innerHTML = '<a href="https://github.com/LukePrior/nbn-upgrade-map" target="_blank" style="color: #000000;">View on GitHub</a> | <a href="https://lukeprior.github.io/nbn-upgrade-map/stats" target="_blank" style="color: #000000;">Stats</a>';
    return div;
}
github.addTo(map);

/**
 * Determines the dot type (color and label) for an address based on its NBN technology and upgrade status.
 * 
 * Priority order (higher checks take precedence):
 * 1. Already has FTTP (Dark Green)
 * 2. Eligible to order upgrade immediately (Medium Green/Blue)
 * 3. Build finalized or upgrade available soon (Light Green/Cyan)
 * 4. Target date within 3 months (Light Green/Cyan)
 * 5. Legacy upgrade records (pre-Nov 2023)
 * 6. Current technology with no upgrade (Yellow/Orange/Red/Dark Red/Gray)
 * 
 * Note: Addresses with future target dates >3 months away will show as their current technology
 * color (e.g., red for FTTN) until the target date is within 3 months.
 * 
 * @param {string} tech - Current NBN technology (e.g., "FTTP", "FTTN", "FTTC")
 * @param {string} upgrade - Upgrade type (e.g., "FTTP_SA", "FTTP_NA")
 * @param {string|null} date - Target eligibility quarter (e.g., "Jun 2024") or null
 * @param {string} status - Tech change status (e.g., "Eligible To Order", "Build Finalised")
 * @param {string} generated - Date string when the data was generated (converted to Date object internally)
 * @returns {Object} Dot type object with label and colour properties
 */
function getDotType(tech, upgrade, date, status, generated) {
    // Already have FTTP
    if (tech == "FTTP") {
        return dotTypes.FTTP;
    }

    // Upgraded to FTTP but previous tech not yet disconnected
    var upgrade_type = upgrade.split("_")[0]
    if (status == "New Tech Connected" && upgrade_type == "FTTP") {
        return dotTypes.FTTP;
    }

    // Eligible for immediate upgrade
    if (status == "Eligible To Order" || status == "Eligible to Order") {
        return (upgrade_type == "FTTP") ? dotTypes.FTTPUpgrade : dotTypes.OtherUpgrade;
    }

    // Eligible for upgrade soon (build complete or in progress)
    if (status == "Build Finalised" || status == "MDU Complex Eligible To Apply" || status == "MDU Complex Premises In Build") {
        return (upgrade_type == "FTTP") ? dotTypes.FTTPUpgradeSoon : dotTypes.OtherUpgradeSoon;
    }

    if (date != null) {
        [month, year] = date.split(" ")
        date = new Date(year, ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].indexOf(month), 1)
    }

    // Calculate date in reference to when data was fetched
    var generated = new Date(generated)
    var diff = (date == null) ? -1 : Math.abs((generated.getFullYear() - date.getFullYear()) * 12 + generated.getMonth() - date.getMonth());

    // Upgrade available in 3 months or less
    // Note: Dates >3 months away will fall through to current tech color below
    if (diff < 3 && diff >= 0) {
        return (upgrade_type == "FTTP") ? dotTypes.FTTPUpgradeSoon : dotTypes.OtherUpgradeSoon;

    } else if (diff == -1) {
        // Legacy FTTP upgrade for records before November 2023
        switch(upgrade) {
            case "FTTP_SA":
                return dotTypes.FTTPUpgrade;
            case "FTTP_NA":
                return dotTypes.FTTPUpgradeSoon;
        }
    }

    // Non FTTP with no upgrade
    switch(tech) {
        case "FTTC":
            return dotTypes.FTTC;
        case "FTTB":
            return dotTypes.FTTN_FTTB;
        case "FTTN":
            return dotTypes.FTTN_FTTB;
        case "HFC":
            return dotTypes.HFC;
        case "WIRELESS":
            return dotTypes.WirelessSat;
        case "SATELLITE":
            return dotTypes.WirelessSat;
        case "NULL":
            return dotTypes.Unknown;
    }

    // This should never happen
    return dotTypes.Unknown;
}

// Australian addresses in this dataset end with a four-digit postcode token.
// Keep the token as a string so leading zeroes survive.
function addressPostcode(name) {
    if (typeof name !== "string") {
        return null;
    }
    var trimmed = name.trim();
    if (!trimmed) {
        return null;
    }
    var parts = trimmed.split(/\s+/);
    var last = parts[parts.length - 1];
    if (/^\d{4}$/.test(last)) {
        return last;
    }
    return null;
}

function featurePostcode(feature) {
    if (!feature || !feature.properties) {
        return null;
    }
    return addressPostcode(feature.properties.name);
}

function postcodesInCollection(data) {
    var seen = {};
    var postcodes = [];
    var features = (data && data.features) ? data.features : [];
    for (var i = 0; i < features.length; i++) {
        var postcode = featurePostcode(features[i]);
        if (postcode != null && !seen[postcode]) {
            seen[postcode] = true;
            postcodes.push(postcode);
        }
    }
    postcodes.sort();
    return postcodes;
}

// A null postcode keeps the full collection, including addresses with no postcode.
function collectionForPostcode(data, postcode) {
    if (data == null) {
        return { type: "FeatureCollection", features: [] };
    }
    if (postcode == null || postcode === "") {
        return data;
    }
    var features = [];
    var source = data.features || [];
    for (var i = 0; i < source.length; i++) {
        if (featurePostcode(source[i]) === postcode) {
            features.push(source[i]);
        }
    }
    var view = {};
    for (var key in data) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            view[key] = data[key];
        }
    }
    view.features = features;
    view.type = data.type || "FeatureCollection";
    return view;
}

// Unknown postcodes and single-postcode suburbs fall back to the full collection.
function resolveActivePostcode(data) {
    var postcodes = postcodesInCollection(data);
    if (postcodes.length < 2) {
        active_postcode = null;
    } else if (active_postcode != null && postcodes.indexOf(active_postcode) === -1) {
        active_postcode = null;
    }
    return postcodes;
}

function shouldFitSuburb(first_load) {
    var tempUrlParams = new URLSearchParams(window.location.search);
    if (tempUrlParams.has("suburb") && tempUrlParams.has("state")) {
        if (default_suburb != tempUrlParams.get("suburb") || default_state != tempUrlParams.get("state") || first_load) {
            return true;
        }
        return false;
    }
    return true;
}

function removeElementsByClass(className) {
    var found = document.getElementsByClassName(className);
    var copy = [];
    for (var i = 0; i < found.length; i++) {
        copy.push(found[i]);
    }
    for (var j = 0; j < copy.length; j++) {
        copy[j].remove();
    }
    return copy.length;
}

function removePostcodeControl() {
    var removed = removeElementsByClass("postcode-selector-container");
    var hosts = document.getElementsByClassName("suburb-selector-container");
    if (removed > 0 && hosts.length > 0) {
        var host = hosts[0];
        host.style.display = "";
        host.style.flexWrap = "";
        host.style.justifyContent = "";
        host.style.alignItems = "";
        host.style.gap = "";
        host.style.maxWidth = "";
    }
}

function ensurePostcodeLayoutStyles() {
    if (!document.getElementById || document.getElementById("postcode-layout-style") || !document.head) {
        return;
    }
    var style = document.createElement("style");
    style.id = "postcode-layout-style";
    style.textContent = ".suburb-selector-container:has(.postcode-selector-container){display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:6px;max-width:calc(100vw - 56px);}" +
        ".suburb-selector-container:has(.postcode-selector-container) .select2-container{max-width:calc(100vw - 56px)!important;min-width:0!important;width:min(300px,calc(100vw - 160px))!important;}" +
        ".postcode-selector-container{max-width:calc(100vw - 56px);}";
    document.head.appendChild(style);
}

function updatePostcodeControl(postcodes, selected) {
    removePostcodeControl();
    if (!postcodes || postcodes.length < 2) {
        return;
    }
    ensurePostcodeLayoutStyles();
    var hosts = document.getElementsByClassName("suburb-selector-container");
    if (hosts.length === 0) {
        return;
    }
    var host = hosts[0];
    host.style.display = "flex";
    host.style.flexWrap = "wrap";
    host.style.justifyContent = "flex-end";
    host.style.alignItems = "center";
    host.style.gap = "6px";
    host.style.maxWidth = "calc(100vw - 56px)";

    var label = document.createElement("label");
    label.className = "postcode-selector-container";
    label.htmlFor = "postcode";
    label.style.backgroundColor = "#ffffff";
    label.style.opacity = "0.95";
    label.style.padding = "4px 6px";
    label.style.borderRadius = "4px";
    label.style.display = "inline-flex";
    label.style.alignItems = "center";
    label.style.gap = "4px";
    label.style.font = "12px/1.2 Arial, sans-serif";
    label.style.maxWidth = "calc(100vw - 56px)";
    label.style.boxSizing = "border-box";
    label.style.flex = "0 0 auto";

    var caption = document.createElement("span");
    caption.className = "postcode-selector-label";
    caption.textContent = "Postcode";
    label.appendChild(caption);

    var select = document.createElement("select");
    select.id = "postcode";
    select.className = "postcode-selector";
    select.style.maxWidth = "46vw";
    select.setAttribute("aria-label", "Postcode");

    function addOption(value, text, isSelected) {
        var opt = document.createElement("option");
        opt.value = value;
        opt.textContent = text;
        if (isSelected) {
            opt.selected = true;
        }
        select.appendChild(opt);
    }
    addOption("", "All postcodes", !selected);
    for (var i = 0; i < postcodes.length; i++) {
        addOption(postcodes[i], postcodes[i], postcodes[i] === selected);
    }
    select.onchange = function () {
        selectPostcode(select.value);
    };
    label.appendChild(select);
    host.appendChild(label);
}

function selectPostcode(value) {
    if (loaded_collection == null || !loaded_state_file) {
        return;
    }
    active_postcode = (value == null || value === "") ? null : String(value);
    var postcodes = resolveActivePostcode(loaded_collection);
    updatePostcodeControl(postcodes, active_postcode);
    // Refit even when state and suburb are unchanged.
    renderSuburbFeatures(collectionForPostcode(loaded_collection, active_postcode), loaded_state_file, default_commit, true);
    applied_postcode = active_postcode;
}

// Draw markers, legend, statistics, description and bounds for one feature collection.
function renderSuburbFeatures(data, state_file, commit, fit) {
        if (data == null) {
            data = { type: "FeatureCollection", features: [] };
        }
        if (!data.features) {
            data.features = [];
        }
        // Update site description
        updateSiteDetailed(default_suburb, default_state, data);
        // clear existing markers
        map.eachLayer(function (layer) {
            if (layer instanceof L.MarkerClusterGroup) {
                map.removeLayer(layer);
            }
        });
        var markers = L.markerClusterGroup({
            chunkedLoading: true,
            chunkInterval: 100,
            chunkDelay: 20,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: false,
            maxClusterRadius: 0,
            iconCreateFunction: function(cluster) {
                children = cluster.getAllChildMarkers();
                var colours = [];

                for (var child of children) {
                    colours.push(child.options.fillColor);
                }

                var color = colours.sort((a, b) =>
                    colours.filter(v => v === a).length
                    - colours.filter(v => v === b).length
                ).pop();

                return L.divIcon({ html: '<div style="background-color: ' + color + '">' + cluster.getChildCount() + '</div>', className: 'marker-cluster' });
            }
        });
        markers.on('clustermouseover', function (a) {
            if (map.getZoom() > 17) {
                a.layer.spiderfy();
            }
        });
        // add circle marker for each feature
        var foundDotTypes = new Set();
        var geojson = L.geoJson(data, {
            pointToLayer: function (feature, latlng) {
                var props = (feature && feature.properties) ? feature.properties : {};
                var dotType = getDotType(props.tech, props.upgrade || "", props.target_eligibility_quarter, props.tech_change_status, data.generated);
                foundDotTypes.add(dotType);
                return L.circleMarker(latlng, {
                    radius: 5,
                    fillColor: dotType.colour,
                    color: "#000000",
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                });
            },
            onEachFeature: function (feature, layer) {
                // popup with place name and upgrade type
                var props = (feature && feature.properties) ? feature.properties : {};
                var s = "<b>" + props.name + " (" + default_state + ")</b><br>Location: " + props.locID + "<br>Current tech: " + props.tech
                // legacy FTTP upgrade pre November 2023
                if (!("target_eligibility_quarter" in props) && props.tech != "FTTP" && (props.tech == "FTTN" || props.tech == "FTTC")) {
                    s += "<br>Upgrade available: " + (props.upgrade == "FTTP_SA" ? "Yes" : (props.upgrade == "FTTP_NA" ? "Soon" : "No"))
                }
                if ("tech_change_status" in props) {
                    s += "<br>Tech Change Status: " + props.tech_change_status
                    if ("upgrade" in props && props.upgrade != "NULL_NA") {
                        s += " (" + props.upgrade.split("_")[0] + ")"
                    }
                }
                if ("program_type" in props) {
                    s += "<br>Program Type: " + props.program_type
                }
                if ("target_eligibility_quarter" in props) {
                    s += "<br>Target Eligibility Quarter: " + props.target_eligibility_quarter
                }

                layer.bindPopup(s);
            }
        })

        // add legend
        var legend = L.control({ position: 'bottomright' });
        legend.onAdd = function (map) {
            var div = L.DomUtil.create('div', 'info legend');
            // include a opacity background over legend
            div.style.backgroundColor = "#ffffff";
            div.style.opacity = "0.8";
            div.style.padding = "5px";
            div.style.borderRadius = "5px";
            div.style.width = "150px";

            var legendHTML = '';
            for (const [key, value] of Object.entries(dotTypes)) {
                if (foundDotTypes.has(value)) {
                    legendHTML += `<svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="${value.colour}" stroke="#000000" stroke-width="1" opacity="1" fill-opacity="0.8" /></svg> ${value.label}<br>`;

                }
            }
            div.innerHTML = legendHTML;
            return div;
        }
        if (document.getElementsByClassName("legend").length > 0) {
            document.getElementsByClassName("legend")[0].remove();
        }
        legend.addTo(map);

        map.addLayer(markers);
        markers.addLayer(geojson);
        // Create stats table
        var stats = L.control({ position: 'bottomright' });
        stats.onAdd = function (map) {
            var div = L.DomUtil.create('div', 'stats');
            div.style.backgroundColor = "#ffffff";
            div.style.opacity = "0.8";
            div.style.padding = "5px";
            div.style.borderRadius = "5px";
            div.style.width = "150px";
            var statsHTML = '<table><tr><th>Technology</th><th>Count</th></tr>';
            var techs = {};
            for (var feature in data["features"]) {
                feature = data["features"][feature];
                var tech = feature && feature.properties ? feature.properties.tech : undefined;
                if (tech == null) {
                    continue;
                }
                if (tech in techs) {
                    techs[tech] += 1;
                } else {
                    techs[tech] = 1;
                }
            }
            techs = Object.fromEntries(Object.entries(techs).sort(([, a], [, b]) => b - a));
            for (var tech in techs) {
                statsHTML += '<tr><td>' + tech + '</td><td>' + techs[tech] + '</td></tr>';
            }
            statsHTML += '</table>';
            statsHTML += 'As of ' + new Date(data["generated"]).toLocaleDateString("en-AU");
            [state, file] = state_file.split('/')
            if (combined_info != null) {
                for (var suburb of combined_info[state]) {
                        this_file = suburb.name.toLowerCase().replace(/ /g, "-") // any other sanitisation required? apostrophe OK
                        if (this_file == file) {
                            if (suburb.announced_date != null) {
                                statsHTML += '<br/>Expected: ' + suburb.announced_date;
                            }
                            break;
                        }
                }
            }

            div.innerHTML = statsHTML;
            return div;
        }
        if (document.getElementsByClassName("stats").length > 0) {
            document.getElementsByClassName("stats")[0].remove();
        }
        stats.addTo(map);

        if (fit) {
            var bounds = geojson.getBounds();
            if (bounds && typeof bounds.isValid === "function" && bounds.isValid()) {
                map.fitBounds(bounds);
            }
        }

        // update url; omit postcode for the All view so legacy links stay stable
        var nextUrl = "?suburb=" + state_file.split("/").pop() + "&state=" + state_file.split("/")[0] + "&commit=" + commit;
        if (active_postcode) {
            nextUrl += "&postcode=" + encodeURIComponent(active_postcode);
        }
        window.history.pushState("", "", nextUrl);
}

// load GeoJSON from an external file
function loadSuburb(state_file, commit, first_load=false) {
    if (state_file == "") {
        return;
    }
    var serial = ++load_serial;
    var next_state = state_file.split("/")[0];
    var next_suburb = state_file.split("/")[1];
    var suburb_changed = default_state !== next_state || default_suburb !== next_suburb;
    if (suburb_changed) {
        active_postcode = null;
        removePostcodeControl();
    }
    url = "https://cdn.jsdelivr.net/gh/LukePrior/nbn-upgrade-map@" + commit + "/results/" + state_file + ".geojson"
    default_state = next_state
    default_suburb = next_suburb
    default_commit = commit
    updateSiteDetails(default_suburb, default_state);
    addControlWithHTML('date-selector', 'Loading...')
    fetch(url).then(res => res.json()).then(data => {
        if (serial !== load_serial) {
            return;
        }
        // Choices come from the full collection; rendering uses the filtered view.
        loaded_collection = data;
        loaded_state_file = state_file;
        var postcodes = resolveActivePostcode(data);
        // Fit on the first paint and whenever the visible postcode changes.
        // A repeated load of the same URL (the suburb control also fires change) must still fit once.
        var fit = shouldFitSuburb(first_load) || applied_postcode !== active_postcode;
        updatePostcodeControl(postcodes, active_postcode);
        renderSuburbFeatures(collectionForPostcode(data, active_postcode), state_file, commit, fit);
        applied_postcode = active_postcode;

        commits_url = "https://api.github.com/repos/LukePrior/nbn-upgrade-map/commits?path=results/" + state_file + ".geojson"
        fetch(commits_url).then(res => res.json()).then(data => {
            if (serial !== load_serial) {
                return;
            }
            var dropdownHTML = '<select id="commit" class="commit-selector" onchange="loadSuburb(default_state+&quot;/&quot;+default_suburb, this.value)" style="width: 120px;">';
            for (const [cid, commit] of Object.entries(data)) {
                [commit_date, commit_time] = commit.commit.author.date.split('T')
                commit_date_js = new Date(commit_date)
                // NBN changed field meanings and we didn't capture new fields
                if (commit_date_js >= new Date(2023, 9, 22) && commit_date_js <= new Date(2023, 10, 4)) {
                    continue;
                }
                // Commits where files were deleted or otherwise corrupted
                if (["7473d0340b2c0903276f1ecce2e3a10c3a35061f"].includes(commit.sha)) {
                    continue;
                }
                selected_text = (commit.sha == default_commit) ? "selected" : ""
                dropdownHTML += '<option value=' + commit.sha + ' ' + selected_text + '>' + new Date(commit_date).toLocaleDateString("en-AU") + '</option>';
            }
            dropdownHTML += '</select>';
            addControlWithHTML('date-selector', dropdownHTML)
            $('.commit-selector').select2();
        });

        gtag('event', 'suburb_load', { 'suburb': default_suburb, 'state': default_state, 'commit': commit });
    });
}

if (default_suburb != null && default_state != null) {
    loadSuburb(default_state + "/" + default_suburb, default_commit, true);
}
