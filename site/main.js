// Load service worker if supported
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/serviceworker.js');
    });
}

// initialize the map
var map = L.map('map', {
    renderer: L.canvas(),
});

map.setView([-27.5, 133], 5);

// load a tile layer
L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    crossOrigin: true,
    maxZoom: 20
}).addTo(map);

// get url parameters
var urlParams = new URLSearchParams(window.location.search);
var default_suburb = null;
var default_state = null;
var default_commit = "latest";
var combined_info = null;
if (urlParams.has("suburb") && urlParams.has("state")) {
    default_suburb = urlParams.get("suburb");
    default_state = urlParams.get("state");
    updateSiteDetails(default_suburb, default_state);
}
if (urlParams.has("commit")) {
    default_commit = urlParams.get("commit");
    default_commit = default_commit == "main" ? "latest" : default_commit;
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

function getDotType(tech, upgrade, date, status, generated) {
    // Already have FTTP
    if (tech == "FTTP") {
        return dotTypes.FTTP;
    }

    // Upgraded to FTTP but previous tech not yet disconnected
    upgrade_type = upgrade.split("_")[0]
    if (status == "New Tech Connected" && upgrade_type == "FTTP") {
        return dotTypes.FTTP;
    }

    // Eligible for immediate upgrade
    if (status == "Eligible To Order" || status == "Eligible to Order") {
        return (upgrade_type == "FTTP") ? dotTypes.FTTPUpgrade : dotTypes.OtherUpgrade;
    }

    // Eligible for upgrade soon
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

// load GeoJSON from an external file
function loadSuburb(state_file, commit, first_load=false) {
    if (state_file == "") {
        return;
    }
    url = "https://cdn.jsdelivr.net/gh/LukePrior/nbn-upgrade-map@" + commit + "/results/" + state_file + ".geojson"
    default_state = state_file.split('/')[0]
    default_suburb = state_file.split('/')[1]
    default_commit = commit
    updateSiteDetails(default_suburb, default_state);
    addControlWithHTML('date-selector', 'Loading...')
    fetch(url).then(res => res.json()).then(data => {
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
                var dotType = getDotType(feature.properties.tech, feature.properties.upgrade, feature.properties.target_eligibility_quarter, feature.properties.tech_change_status, data.generated);
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
                var s = "<b>" + feature.properties.name + " (" + default_state + ")</b><br>Location: " + feature.properties.locID + "<br>Current tech: " + feature.properties.tech
                // legacy FTTP upgrade pre November 2023
                if (!("target_eligibility_quarter" in feature.properties) && feature.properties.tech != "FTTP" && (feature.properties.tech == "FTTN" || feature.properties.tech == "FTTC")) {
                    s += "<br>Upgrade available: " + (feature.properties.upgrade == "FTTP_SA" ? "Yes" : (feature.properties.upgrade == "FTTP_NA" ? "Soon" : "No"))
                }
                if ("tech_change_status" in feature.properties) {
                    s += "<br>Tech Change Status: " + feature.properties.tech_change_status
                    if ("upgrade" in feature.properties && feature.properties.upgrade != "NULL_NA") {
                        s += " (" + feature.properties.upgrade.split("_")[0] + ")"
                    }
                }
                if ("program_type" in feature.properties) {
                    s += "<br>Program Type: " + feature.properties.program_type
                }
                if ("target_eligibility_quarter" in feature.properties) {
                    s += "<br>Target Eligibility Quarter: " + feature.properties.target_eligibility_quarter
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
                if (feature.properties.tech in techs) {
                    techs[feature.properties.tech] += 1;
                } else {
                    techs[feature.properties.tech] = 1;
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

        var tempUrlParams = new URLSearchParams(window.location.search);

        if (tempUrlParams.has("suburb") && tempUrlParams.has("state")) {
            if (default_suburb != tempUrlParams.get("suburb") || default_state != tempUrlParams.get("state") || first_load) {
                map.fitBounds(geojson.getBounds());
            }
        } else {
            map.fitBounds(geojson.getBounds());
        }

        // update url
        window.history.pushState("", "", "?suburb=" + url.split("/").pop().split(".")[0] + "&state=" + url.split("/").slice(-2)[0] + "&commit=" + commit);

        commits_url = "https://api.github.com/repos/LukePrior/nbn-upgrade-map/commits?path=results/" + state_file + ".geojson"
        fetch(commits_url).then(res => res.json()).then(data => {
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
