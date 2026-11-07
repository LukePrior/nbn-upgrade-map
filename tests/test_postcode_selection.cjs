const test = require('node:test');
const assert = require('node:assert/strict');

// Values created inside the app sandbox are arrays from another realm.
function expectEqual(actual, expected) {
    assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected);
}
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const mainSource = fs.readFileSync(path.join(__dirname, '..', 'site', 'main.js'), 'utf8');

// Minimal browser stand-ins. Production main.js runs unmodified against them.
const prelude = `
function DOMElement(tag) {
    this.tagName = String(tag || "div").toUpperCase();
    this.className = "";
    this.id = "";
    this.children = [];
    this.parentNode = null;
    this.style = {};
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.selected = false;
    this.attributes = {};
    this.onchange = null;
    this.htmlFor = "";
}
DOMElement.prototype.appendChild = function (child) {
    if (child && child.remove) child.remove();
    child.parentNode = this;
    this.children.push(child);
    return child;
};
DOMElement.prototype.remove = function () {
    if (!this.parentNode) return;
    var index = this.parentNode.children.indexOf(this);
    if (index >= 0) this.parentNode.children.splice(index, 1);
    this.parentNode = null;
};
DOMElement.prototype.setAttribute = function (name, value) {
    this.attributes[name] = String(value);
    if (name === "id") this.id = String(value);
    if (name === "class") this.className = String(value);
};
DOMElement.prototype.getAttribute = function (name) {
    return this.attributes[name];
};
DOMElement.prototype.querySelectorAll = function (selector) {
    var all = [];
    walkElements(this, all);
    if (selector !== ".select2-container") return [];
    var found = [];
    for (var i = 0; i < all.length; i++) {
        if (String(all[i].className || "").split(/\\s+/).indexOf("select2-container") !== -1) found.push(all[i]);
    }
    return found;
};

function walkElements(el, out) {
    if (!el || typeof el !== "object") return;
    out.push(el);
    var kids = el.children || [];
    for (var i = 0; i < kids.length; i++) walkElements(kids[i], out);
}

var document = {
    title: "NBN Technology Map",
    _description: "",
    createElement: function (tag) {
        var el = new DOMElement(tag);
        if (el.tagName === "SELECT") {
            Object.defineProperty(el, "value", {
                configurable: true,
                enumerable: true,
                get: function () {
                    var opts = el.children.filter(function (child) { return child.tagName === "OPTION"; });
                    for (var i = 0; i < opts.length; i++) {
                        if (opts[i].selected) return opts[i].value;
                    }
                    return opts.length ? opts[0].value : "";
                },
                set: function (value) {
                    var opts = el.children.filter(function (child) { return child.tagName === "OPTION"; });
                    for (var i = 0; i < opts.length; i++) {
                        opts[i].selected = String(opts[i].value) === String(value);
                    }
                }
            });
        }
        return el;
    },
    getElementsByClassName: function (name) {
        var all = [];
        walkElements(document.documentElement, all);
        var matches = [];
        for (var i = 0; i < all.length; i++) {
            if (String(all[i].className || "").split(/\\s+/).indexOf(name) !== -1) matches.push(all[i]);
        }
        return matches;
    },
    getElementById: function (id) {
        var all = [];
        walkElements(document.documentElement, all);
        for (var i = 0; i < all.length; i++) {
            if (all[i].id === id) return all[i];
        }
        return null;
    }
};
document.documentElement = new DOMElement("html");
document.head = new DOMElement("head");
document.body = new DOMElement("body");
document.documentElement.appendChild(document.head);
document.documentElement.appendChild(document.body);

function MarkerClusterGroup() {}

var L = {
    canvas: function () { return {}; },
    map: function () {
        var mapEl = document.createElement("div");
        mapEl.id = "map";
        document.body.appendChild(mapEl);
        var corners = {};
        ["topright", "topleft", "bottomright", "bottomleft"].forEach(function (pos) {
            var corner = document.createElement("div");
            corner.className = "leaflet-" + pos;
            corners[pos] = corner;
            mapEl.appendChild(corner);
        });
        return {
            _corners: corners,
            _layers: [],
            _fitCalls: [],
            setView: function () {},
            addLayer: function (layer) { this._layers.push(layer); },
            removeLayer: function (layer) {
                this._layers = this._layers.filter(function (candidate) { return candidate !== layer; });
            },
            eachLayer: function (fn) { this._layers.slice().forEach(fn); },
            fitBounds: function (bounds) {
                if (!bounds || typeof bounds.isValid !== "function" || !bounds.isValid()) {
                    throw new Error("fitBounds called with invalid bounds");
                }
                this._fitCalls.push(bounds);
            },
            on: function () { return this; },
            getZoom: function () { return 5; }
        };
    },
    maplibreGL: function () {
        return { addTo: function () { return this; } };
    },
    DomUtil: {
        create: function (tag, className) {
            var el = document.createElement(tag);
            if (className) el.className = className;
            return el;
        }
    },
    control: function (options) {
        return {
            options: options || {},
            onAdd: null,
            addTo: function (map) {
                var el = this.onAdd(map);
                var pos = ((this.options && this.options.position) || "topright").toLowerCase();
                (map._corners[pos] || map._corners.topright).appendChild(el);
                return this;
            }
        };
    },
    MarkerClusterGroup: MarkerClusterGroup,
    markerClusterGroup: function (opts) {
        var group = Object.create(MarkerClusterGroup.prototype);
        group._layers = [];
        group.options = opts;
        group.on = function () { return group; };
        group.addLayer = function (layer) { group._layers.push(layer); return group; };
        return group;
    },
    divIcon: function (opts) { return opts || {}; },
    circleMarker: function (latlng, opts) {
        return {
            _latlng: latlng,
            options: opts || {},
            bindPopup: function (html) { this._popup = html; return this; }
        };
    },
    geoJson: function (data, options) {
        var features = (data && data.features) || [];
        var layers = [];
        for (var i = 0; i < features.length; i++) {
            var feature = features[i];
            var coords = (feature.geometry && feature.geometry.coordinates) || [0, 0];
            var latlng = { lng: Number(coords[0]), lat: Number(coords[1]) };
            var marker = options && options.pointToLayer ? options.pointToLayer(feature, latlng) : null;
            if (options && options.onEachFeature) {
                options.onEachFeature(feature, marker || { bindPopup: function () {} });
            }
            layers.push({ feature: feature, latlng: latlng, marker: marker });
        }
        return {
            _layers: layers,
            getBounds: function () {
                if (!layers.length) return { isValid: function () { return false; } };
                var south = Infinity, north = -Infinity, west = Infinity, east = -Infinity;
                for (var j = 0; j < layers.length; j++) {
                    var latlng = layers[j].latlng;
                    if (latlng.lat < south) south = latlng.lat;
                    if (latlng.lat > north) north = latlng.lat;
                    if (latlng.lng < west) west = latlng.lng;
                    if (latlng.lng > east) east = latlng.lng;
                }
                if (!isFinite(south) || !isFinite(west)) return { isValid: function () { return false; } };
                return {
                    isValid: function () { return true; },
                    south: south,
                    north: north,
                    west: west,
                    east: east
                };
            }
        };
    }
};

function $(selector) {
    var api = {
        select2: function () { return api; },
        append: function () { return api; },
        trigger: function () { return api; },
        ready: function (fn) { fn(); return api; },
        on: function () { return api; },
        attr: function (name, value) {
            if (String(selector).indexOf("description") !== -1) {
                if (arguments.length < 2) return document._description;
                document._description = value;
            }
            return api;
        }
    };
    return api;
}
$.ajax = function () {
    var request = {
        then: function () { return request; },
        fail: function () { return request; }
    };
    return request;
};

var localStorage = (function () {
    var mem = {};
    return {
        getItem: function (key) {
            return Object.prototype.hasOwnProperty.call(mem, key) ? mem[key] : null;
        },
        setItem: function (key, value) { mem[key] = String(value); },
        removeItem: function (key) { delete mem[key]; }
    };
})();

var navigator = {};
var location = { search: this.__search || "", href: "http://localhost/" };
var history = {
    stack: [],
    pushState: function (_state, _title, url) {
        history.stack.push(String(url));
        location.search = String(url);
    }
};
var window = this;
window.location = location;
window.history = history;
window.matchMedia = function () { return { matches: false }; };
window.addEventListener = function () {};
function gtag() {}
function Option(text, value, defaultSelected, selected) {
    this.text = text;
    this.value = value;
    this.defaultSelected = defaultSelected;
    this.selected = selected;
}
function fetch(url) {
    fetch.calls.push(String(url));
    var body;
    var source = this.__geojson;
    if (String(url).indexOf("combined-suburbs") !== -1) {
        body = { NSW: [{ name: "The Rocks" }] };
    } else if (String(url).indexOf("api.github.com") !== -1) {
        body = [{ sha: "abc123def", commit: { author: { date: "2024-06-01T00:00:00Z" } } }];
    } else if (typeof source === "function") {
        body = source(url);
    } else if (source) {
        body = source;
    } else {
        body = { type: "FeatureCollection", generated: "2024-05-27T00:00:00.000Z", features: [] };
    }
    return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve(body); }
    });
}
fetch.calls = [];
`;

function loadApp(search, geojson) {
    const sandbox = {
        console,
        URLSearchParams,
        encodeURIComponent,
        decodeURIComponent,
        Promise,
        Object,
        Array,
        String,
        Number,
        Boolean,
        Date,
        Math,
        JSON,
        RegExp,
        Error,
        Set,
        Map,
        parseInt,
        parseFloat,
        isNaN,
        isFinite,
        Infinity,
        NaN,
        __search: search || '',
        __geojson: geojson || null,
    };
    vm.runInNewContext(prelude, sandbox, { filename: 'tests/dom-leaflet-stub.js' });
    vm.runInNewContext(mainSource, sandbox, { filename: 'site/main.js' });
    return sandbox;
}

async function flush() {
    for (let i = 0; i < 8; i++) {
        await new Promise((resolve) => setImmediate(resolve));
    }
}

function feature(name, lng, lat, tech, extra) {
    const properties = Object.assign({
        name,
        tech: tech || 'FTTP',
        upgrade: 'NULL_NA',
        locID: 'LOC-' + String(name),
        tech_change_status: 'Not Planned',
        target_eligibility_quarter: null,
    }, extra || {});
    return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties,
    };
}

function collection(features, generated) {
    return {
        type: 'FeatureCollection',
        generated: generated || '2024-05-27T00:00:00.000Z',
        features,
    };
}

const SYDNEY = [151.2093, -33.8599];
const BATHURST = [149.5775, -33.4193];

function rocksCollection() {
    return collection([
        feature('1 GEORGE STREET THE ROCKS 2000', 151.2093, -33.8599, 'FTTP'),
        feature('2 GEORGE STREET THE ROCKS 2000', 151.2108, -33.8606, 'FTTP'),
        feature('164 BACK SWAMP ROAD THE ROCKS 2795', 149.5775, -33.4193, 'FTTN'),
        feature('10 CHURCH LANE THE ROCKS 2795', 149.5810, -33.4212, 'FTTN'),
    ]);
}

function renderedItems(sandbox) {
    const items = [];
    for (const layer of sandbox.map._layers) {
        if (!layer || !Array.isArray(layer._layers)) continue;
        for (const geo of layer._layers) {
            for (const item of geo._layers || []) items.push(item);
        }
    }
    return items;
}

function renderedNames(sandbox) {
    return renderedItems(sandbox).map((item) => item.feature && item.feature.properties ? item.feature.properties.name : undefined).sort();
}

function postcodeLabel(sandbox) {
    const nodes = sandbox.document.getElementsByClassName('postcode-selector-container');
    return nodes.length ? nodes[0] : null;
}

function postcodeSelect(sandbox) {
    const label = postcodeLabel(sandbox);
    if (!label) return null;
    for (const child of label.children) {
        if (child.tagName === 'SELECT') return child;
    }
    return null;
}

function optionSnapshot(select) {
    return select.children.filter((child) => child.tagName === 'OPTION').map((option) => ({
        value: option.value,
        text: option.textContent,
        selected: !!option.selected,
    }));
}

function htmlByClass(sandbox, className) {
    const nodes = sandbox.document.getElementsByClassName(className);
    if (!nodes.length) return '';
    return nodes[nodes.length - 1].innerHTML;
}

function paramsOf(sandbox) {
    return new URLSearchParams(sandbox.location.search);
}

test('address postcodes keep a terminal four-digit token, including leading zeroes', () => {
    const sandbox = loadApp('');
    assert.equal(sandbox.addressPostcode('1 EXAMPLE STREET 0800'), '0800');
    assert.equal(sandbox.addressPostcode('  2 EXAMPLE STREET 2000  '), '2000');
    assert.equal(sandbox.addressPostcode('PO BOX 12 SUBURB 0210'), '0210');
    assert.equal(sandbox.addressPostcode('NO POSTCODE HERE'), null);
    assert.equal(sandbox.addressPostcode('ROAD 12345'), null);
    assert.equal(sandbox.addressPostcode('ROAD 2000 EXTRA'), null);
    assert.equal(sandbox.addressPostcode('ROAD 200'), null);
    assert.equal(sandbox.addressPostcode(''), null);
    assert.equal(sandbox.addressPostcode('   '), null);
    assert.equal(sandbox.addressPostcode(null), null);
    assert.equal(sandbox.addressPostcode(undefined), null);
    assert.equal(sandbox.addressPostcode(2000), null);
    assert.equal(sandbox.featurePostcode({ properties: {} }), null);
    assert.equal(sandbox.featurePostcode({}), null);
    assert.equal(sandbox.featurePostcode(null), null);

    const grouped = sandbox.postcodesInCollection(collection([
        feature('A STREET 2000', 151.2, -33.86, 'FTTP'),
        feature('B STREET 0800', 130.8, -12.4, 'FTTN'),
        feature('C STREET 0800', 130.9, -12.5, 'FTTN'),
        feature('NOT AN ADDRESS', 133, -25, 'HFC'),
        { type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] } },
    ]));
    expectEqual(grouped, ['0800', '2000']);

    const source = collection([
        feature('KEEP ME 2000', 151.2, -33.86, 'FTTP'),
        feature('NO CODE', 149.5, -33.4, 'FTTN'),
    ]);
    assert.equal(sandbox.collectionForPostcode(source, null), source);
    assert.equal(sandbox.collectionForPostcode(source, '').features.length, 2);
    expectEqual(
        sandbox.collectionForPostcode(source, '2000').features.map((item) => item.properties.name),
        ['KEEP ME 2000']
    );
});

test('distant postcodes can be chosen independently and All restores both', async () => {
    const sandbox = loadApp('');
    sandbox.__geojson = rocksCollection();
    sandbox.loadSuburb('NSW/the-rocks', 'latest', true);
    await flush();

    const label = postcodeLabel(sandbox);
    assert.ok(label);
    const caption = label.children.find((child) => child.className === 'postcode-selector-label');
    assert.equal(caption.textContent, 'Postcode');
    const select = postcodeSelect(sandbox);
    assert.equal(typeof select.onchange, 'function');
    assert.match(String(select.onchange), /selectPostcode/);
    expectEqual(optionSnapshot(select).map((option) => option.text), ['All postcodes', '2000', '2795']);
    assert.equal(select.value, '');
    const host = sandbox.document.getElementsByClassName('suburb-selector-container')[0];
    assert.equal(host.style.display, 'flex');
    assert.equal(host.style.flexWrap, 'wrap');
    assert.match(host.style.maxWidth, /100vw/);

    expectEqual(renderedNames(sandbox), [
        '1 GEORGE STREET THE ROCKS 2000',
        '10 CHURCH LANE THE ROCKS 2795',
        '164 BACK SWAMP ROAD THE ROCKS 2795',
        '2 GEORGE STREET THE ROCKS 2000',
    ]);
    const initialBounds = sandbox.map._fitCalls[sandbox.map._fitCalls.length - 1];
    assert.ok(initialBounds.west < 149.6 && initialBounds.east > 151.2);
    assert.match(htmlByClass(sandbox, 'stats'), /FTTP/);
    assert.match(htmlByClass(sandbox, 'stats'), /FTTN/);
    assert.match(htmlByClass(sandbox, 'legend'), /FTTP/);
    assert.match(htmlByClass(sandbox, 'legend'), /FTTN\/FTTB/);
    assert.match(sandbox.document._description, /FTTP/);
    assert.match(sandbox.document._description, /FTTN/);
    assert.equal(paramsOf(sandbox).get('postcode'), null);
    assert.equal(paramsOf(sandbox).get('suburb'), 'the-rocks');

    sandbox.map._fitCalls = [];
    select.value = '2000';
    select.onchange();
    expectEqual(renderedNames(sandbox), [
        '1 GEORGE STREET THE ROCKS 2000',
        '2 GEORGE STREET THE ROCKS 2000',
    ]);
    const sydney = sandbox.map._fitCalls[sandbox.map._fitCalls.length - 1];
    assert.ok(sydney.west > 151.2 && sydney.east < 151.22);
    assert.ok(sydney.south < -33.85 && sydney.north > -33.87);
    assert.match(htmlByClass(sandbox, 'stats'), /<td>FTTP<\/td><td>2<\/td>/);
    assert.doesNotMatch(htmlByClass(sandbox, 'stats'), /FTTN/);
    assert.match(htmlByClass(sandbox, 'legend'), /FTTP/);
    assert.doesNotMatch(htmlByClass(sandbox, 'legend'), /FTTN/);
    assert.match(sandbox.document._description, /FTTP/);
    assert.doesNotMatch(sandbox.document._description, /FTTN/);
    assert.equal(paramsOf(sandbox).get('postcode'), '2000');
    assert.equal(paramsOf(sandbox).get('suburb'), 'the-rocks');
    assert.equal(paramsOf(sandbox).get('state'), 'NSW');
    assert.equal(postcodeSelect(sandbox).value, '2000');
    assert.match(renderedItems(sandbox)[0].marker._popup, /GEORGE STREET THE ROCKS 2000/);

    sandbox.map._fitCalls = [];
    const bathurstSelect = postcodeSelect(sandbox);
    bathurstSelect.value = '2795';
    bathurstSelect.onchange();
    expectEqual(renderedNames(sandbox), [
        '10 CHURCH LANE THE ROCKS 2795',
        '164 BACK SWAMP ROAD THE ROCKS 2795',
    ]);
    const bathurst = sandbox.map._fitCalls[sandbox.map._fitCalls.length - 1];
    assert.ok(bathurst.west > 149.57 && bathurst.east < 149.59);
    assert.ok(bathurst.north < -33.41 && bathurst.south > -33.43);
    assert.match(htmlByClass(sandbox, 'stats'), /<td>FTTN<\/td><td>2<\/td>/);
    assert.doesNotMatch(htmlByClass(sandbox, 'stats'), /FTTP/);
    assert.equal(paramsOf(sandbox).get('postcode'), '2795');

    const allSelect = postcodeSelect(sandbox);
    allSelect.value = '';
    allSelect.onchange();
    assert.equal(renderedNames(sandbox).length, 4);
    const restored = sandbox.map._fitCalls[sandbox.map._fitCalls.length - 1];
    assert.ok(restored.west < 149.6 && restored.east > 151.2);
    assert.equal(paramsOf(sandbox).get('postcode'), null);
    assert.equal(postcodeSelect(sandbox).value, '');
    assert.match(htmlByClass(sandbox, 'stats'), /FTTP/);
    assert.match(htmlByClass(sandbox, 'stats'), /FTTN/);
});

test('a postcode URL reloads the same markers, statistics, legend and description', async () => {
    const opened = loadApp('?suburb=the-rocks&state=NSW&postcode=2000', rocksCollection());
    await flush();
    assert.equal(postcodeSelect(opened).value, '2000');
    expectEqual(optionSnapshot(postcodeSelect(opened)).map((option) => option.value), ['', '2000', '2795']);
    expectEqual(renderedNames(opened), [
        '1 GEORGE STREET THE ROCKS 2000',
        '2 GEORGE STREET THE ROCKS 2000',
    ]);
    const openedSnapshot = {
        names: renderedNames(opened),
        stats: htmlByClass(opened, 'stats'),
        legend: htmlByClass(opened, 'legend'),
        description: opened.document._description,
        postcode: paramsOf(opened).get('postcode'),
    };

    const select = postcodeSelect(opened);
    select.value = '2795';
    select.onchange();
    const reloaded = loadApp(opened.location.search, rocksCollection());
    await flush();
    assert.equal(postcodeSelect(reloaded).value, '2795');
    expectEqual(renderedNames(reloaded), [
        '10 CHURCH LANE THE ROCKS 2795',
        '164 BACK SWAMP ROAD THE ROCKS 2795',
    ]);
    assert.equal(htmlByClass(reloaded, 'stats'), htmlByClass(opened, 'stats'));
    assert.equal(htmlByClass(reloaded, 'legend'), htmlByClass(opened, 'legend'));
    assert.equal(reloaded.document._description, opened.document._description);
    assert.equal(paramsOf(reloaded).get('suburb'), 'the-rocks');
    assert.equal(paramsOf(reloaded).get('state'), 'NSW');
    assert.equal(paramsOf(reloaded).get('postcode'), '2795');
    assert.notEqual(JSON.stringify(renderedNames(reloaded)), JSON.stringify(openedSnapshot.names));
    assert.match(openedSnapshot.description, /FTTP/);
});

test('commit changes keep a valid postcode and fall back to All when it disappears', async () => {
    let current = rocksCollection();
    const sandbox = loadApp('?suburb=the-rocks&state=NSW&postcode=2000', () => current);
    await flush();
    assert.equal(postcodeSelect(sandbox).value, '2000');
    assert.equal(renderedNames(sandbox).length, 2);

    current = rocksCollection();
    sandbox.map._fitCalls = [];
    sandbox.loadSuburb('NSW/the-rocks', 'sha-still-has-2000', false);
    await flush();
    assert.equal(postcodeSelect(sandbox).value, '2000');
    expectEqual(renderedNames(sandbox), [
        '1 GEORGE STREET THE ROCKS 2000',
        '2 GEORGE STREET THE ROCKS 2000',
    ]);
    assert.equal(sandbox.map._fitCalls.length, 0);
    assert.equal(paramsOf(sandbox).get('postcode'), '2000');
    assert.equal(paramsOf(sandbox).get('commit'), 'sha-still-has-2000');
    assert.match(htmlByClass(sandbox, 'date-selector'), /loadSuburb/);

    current = collection([
        feature('10 CHURCH LANE THE ROCKS 2795', 149.5810, -33.4212, 'FTTN'),
        feature('1 MAIN STREET OTHER PLACE 3000', 144.9631, -37.8136, 'HFC'),
    ]);
    sandbox.map._fitCalls = [];
    sandbox.loadSuburb('NSW/the-rocks', 'sha-without-2000', false);
    await flush();
    const select = postcodeSelect(sandbox);
    assert.ok(select);
    assert.equal(select.value, '');
    expectEqual(optionSnapshot(select).map((option) => option.text), ['All postcodes', '2795', '3000']);
    expectEqual(renderedNames(sandbox), [
        '1 MAIN STREET OTHER PLACE 3000',
        '10 CHURCH LANE THE ROCKS 2795',
    ]);
    assert.equal(sandbox.map._fitCalls.length, 1);
    assert.equal(sandbox.map._fitCalls[0].isValid(), true);
    assert.ok(sandbox.map._fitCalls[0].west < 145 && sandbox.map._fitCalls[0].east > 149);
    assert.equal(paramsOf(sandbox).get('postcode'), null);
    assert.match(htmlByClass(sandbox, 'stats'), /FTTN/);
    assert.match(htmlByClass(sandbox, 'stats'), /HFC/);
});

test('changing suburb resets the postcode and drops a stale control', async () => {
    const sandbox = loadApp('');
    const shared = collection([
        feature('1 GEORGE STREET THE ROCKS 2000', SYDNEY[0], SYDNEY[1], 'FTTP'),
        feature('2 OTHER ROAD THE ROCKS 2795', BATHURST[0], BATHURST[1], 'FTTN'),
    ]);
    const nextSuburb = collection([
        feature('9 KING STREET BATHURST 2000', 149.57, -33.42, 'FTTP'),
        feature('8 KING STREET BATHURST 2795', 149.50, -33.40, 'HFC'),
    ]);
    sandbox.__geojson = shared;
    sandbox.loadSuburb('NSW/the-rocks', 'latest', true);
    await flush();
    const select = postcodeSelect(sandbox);
    select.value = '2000';
    select.onchange();
    assert.equal(paramsOf(sandbox).get('postcode'), '2000');

    sandbox.__geojson = nextSuburb;
    sandbox.loadSuburb('NSW/bathurst', 'latest', false);
    assert.equal(postcodeSelect(sandbox), null);
    await flush();
    const reset = postcodeSelect(sandbox);
    assert.ok(reset);
    assert.equal(reset.value, '');
    expectEqual(renderedNames(sandbox), [
        '8 KING STREET BATHURST 2795',
        '9 KING STREET BATHURST 2000',
    ]);
    assert.equal(paramsOf(sandbox).get('suburb'), 'bathurst');
    assert.equal(paramsOf(sandbox).get('postcode'), null);

    sandbox.__geojson = collection([
        feature('1 LONDON CIRCUIT ACTON 2601', 149.13, -35.28, 'FTTP'),
        feature('2 LONDON CIRCUIT ACTON 2601', 149.14, -35.29, 'FTTP'),
    ]);
    sandbox.loadSuburb('ACT/acton', 'latest', false);
    assert.equal(postcodeSelect(sandbox), null);
    await flush();
    assert.equal(postcodeSelect(sandbox), null);
    assert.equal(sandbox.document.getElementsByClassName('suburb-selector-container')[0].style.display, '');
    expectEqual(renderedNames(sandbox), [
        '1 LONDON CIRCUIT ACTON 2601',
        '2 LONDON CIRCUIT ACTON 2601',
    ]);
    assert.equal(paramsOf(sandbox).get('postcode'), null);
    assert.equal(paramsOf(sandbox).get('suburb'), 'acton');
});

test('legacy URLs and single-postcode suburbs keep the unfiltered map', async () => {
    const legacy = loadApp('?suburb=the-rocks&state=NSW', rocksCollection());
    await flush();
    assert.equal(postcodeSelect(legacy).value, '');
    assert.equal(renderedNames(legacy).length, 4);
    assert.equal(paramsOf(legacy).has('postcode'), false);
    assert.equal(paramsOf(legacy).get('commit'), 'latest');

    const single = loadApp('?suburb=acton&state=ACT&postcode=2601', collection([
        feature('1 LONDON CIRCUIT ACTON 2601', 149.13, -35.28, 'FTTP'),
        feature('UNIT WITHOUT A CODE', 149.14, -35.29, 'HFC'),
    ]));
    await flush();
    assert.equal(postcodeSelect(single), null);
    expectEqual(renderedNames(single), [
        '1 LONDON CIRCUIT ACTON 2601',
        'UNIT WITHOUT A CODE',
    ]);
    assert.equal(paramsOf(single).has('postcode'), false);
});

test('leading zeroes, malformed names, unknown postcodes and empty collections stay safe', async () => {
    const mixed = collection([
        feature('1 REMOTE ROAD 0800', 130.84, -12.46, 'FTTP'),
        feature('2 GEORGE STREET 2000', SYDNEY[0], SYDNEY[1], 'FTTN'),
        feature('MALFORMED 12345', 133.0, -25.0, 'HFC'),
        feature('MIDDLE 2000 TOKEN', 134.0, -26.0, 'HFC'),
        feature(null, 135.0, -27.0, 'FTTP', { name: undefined }),
        { type: 'Feature', geometry: { type: 'Point', coordinates: [136.0, -28.0] } },
    ]);
    const sandbox = loadApp('');
    sandbox.__geojson = mixed;
    sandbox.loadSuburb('NT/remote', 'latest', true);
    await flush();
    const select = postcodeSelect(sandbox);
    expectEqual(optionSnapshot(select).map((option) => option.value), ['', '0800', '2000']);
    assert.equal(renderedNames(sandbox).length, 6);

    select.value = '0800';
    select.onchange();
    expectEqual(renderedNames(sandbox), ['1 REMOTE ROAD 0800']);
    assert.equal(paramsOf(sandbox).get('postcode'), '0800');
    assert.match(htmlByClass(sandbox, 'stats'), /<td>FTTP<\/td><td>1<\/td>/);

    postcodeSelect(sandbox).value = '';
    postcodeSelect(sandbox).onchange();
    assert.equal(renderedNames(sandbox).length, 6);
    assert.equal(paramsOf(sandbox).has('postcode'), false);

    const unknown = loadApp('?suburb=remote&state=NT&postcode=9999', mixed);
    await flush();
    assert.equal(postcodeSelect(unknown).value, '');
    assert.equal(renderedNames(unknown).length, 6);
    assert.equal(paramsOf(unknown).has('postcode'), false);
    const bounds = unknown.map._fitCalls[unknown.map._fitCalls.length - 1];
    assert.equal(bounds.isValid(), true);
    assert.ok(bounds.west < 131 && bounds.east > 151);

    const unrecognized = loadApp('');
    unrecognized.__geojson = collection([
        feature('JUST A PLACE', 149.1, -35.2, 'FTTP'),
        feature('STILL NO POSTCODE', 149.2, -35.3, 'HFC'),
    ]);
    unrecognized.loadSuburb('ACT/nameless', 'latest', true);
    await flush();
    assert.equal(postcodeSelect(unrecognized), null);
    assert.equal(renderedNames(unrecognized).length, 2);
    assert.ok(unrecognized.map._fitCalls.length > 0);
    assert.equal(unrecognized.map._fitCalls.at(-1).isValid(), true);

    const empty = loadApp('');
    empty.__geojson = { type: 'FeatureCollection', generated: '2024-05-27T00:00:00.000Z', features: [] };
    empty.loadSuburb('NSW/empty', 'latest', true);
    await flush();
    assert.equal(postcodeSelect(empty), null);
    assert.equal(renderedNames(empty).length, 0);
    assert.equal(empty.map._fitCalls.length, 0);
    assert.match(empty.document._description, /Empty NSW/);

    const blank = loadApp('');
    blank.__geojson = { type: 'FeatureCollection' };
    blank.loadSuburb('NSW/blank', 'latest', true);
    await flush();
    assert.equal(blank.map._fitCalls.length, 0);
    assert.equal(renderedNames(blank).length, 0);

    sandbox.selectPostcode('9999');
    assert.equal(postcodeSelect(sandbox).value, '');
    assert.equal(renderedNames(sandbox).length, 6);
    assert.equal(sandbox.map._fitCalls.at(-1).isValid(), true);
});

test('the first paint fits even when the URL already names the suburb', async () => {
    const sandbox = loadApp('');
    sandbox.default_suburb = 'the-rocks';
    sandbox.default_state = 'NSW';
    sandbox.active_postcode = '2000';
    sandbox.location.search = '?suburb=the-rocks&state=NSW&postcode=2000';
    sandbox.__geojson = rocksCollection();
    sandbox.loadSuburb('NSW/the-rocks', 'latest', false);
    await flush();
    assert.equal(postcodeSelect(sandbox).value, '2000');
    assert.equal(sandbox.map._fitCalls.length, 1);
    const bounds = sandbox.map._fitCalls[0];
    assert.equal(bounds.isValid(), true);
    assert.ok(bounds.west > 151.2 && bounds.east < 151.22);
    expectEqual(renderedNames(sandbox), [
        '1 GEORGE STREET THE ROCKS 2000',
        '2 GEORGE STREET THE ROCKS 2000',
    ]);
});

test('loadSuburb and the postcode handler both render through the production path', async () => {
    const sandbox = loadApp('');
    const rendered = [];
    const original = sandbox.renderSuburbFeatures;
    sandbox.renderSuburbFeatures = function (data, stateFile, commit, fit) {
        rendered.push({
            names: (data.features || []).map((item) => item.properties && item.properties.name),
            stateFile,
            commit,
            fit,
        });
        return original.apply(this, arguments);
    };
    sandbox.__geojson = rocksCollection();
    sandbox.loadSuburb('NSW/the-rocks', 'latest', true);
    await flush();
    assert.equal(rendered.length, 1);
    assert.equal(rendered[0].names.length, 4);
    assert.equal(rendered[0].fit, true);
    assert.equal(rendered[0].stateFile, 'NSW/the-rocks');

    const select = postcodeSelect(sandbox);
    select.value = '2795';
    select.onchange();
    assert.equal(rendered.length, 2);
    expectEqual(rendered[1].names, [
        '164 BACK SWAMP ROAD THE ROCKS 2795',
        '10 CHURCH LANE THE ROCKS 2795',
    ]);
    assert.equal(rendered[1].fit, true);
    assert.equal(rendered[1].commit, 'latest');
    assert.equal(sandbox.map._fitCalls.length >= 2, true);
});
