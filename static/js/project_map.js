(function () {
    "use strict";

    const config = JSON.parse(document.getElementById("project-config").textContent);

    function getCookie(name) {
        const match = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
        return match ? decodeURIComponent(match[2]) : null;
    }

    const csrftoken = getCookie("csrftoken");

    // Get CSS variable colors for map annotations (synchronized with design system)
    function getCSSVar(varName) {
        return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    }

    const mapColors = {
        polygonFill: getCSSVar("--map-color-polygon"),
        line: getCSSVar("--map-color-line"),
        point: getCSSVar("--map-color-point"),
        textColor: getCSSVar("--map-text-color"),
        textHalo: getCSSVar("--map-text-halo"),
    };

    function apiFetch(url, options) {
        options = options || {};
        options.headers = Object.assign({}, options.headers, {
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/json",
        });
        return fetch(url, options).then(function (response) {
            if (!response.ok) {
                return response.text().then(function (text) {
                    throw new Error("Request failed: " + response.status + " " + text);
                });
            }
            return response.status === 204 ? null : response.json();
        });
    }

    function tileUrl() {
        return config.tileUrlTemplate.replace(/0\/0\/0\.png$/, "{z}/{x}/{y}.png");
    }

    function annotationDetailUrl(id) {
        return config.annotationDetailUrlTemplate.replace(/\/0\/$/, "/" + id + "/");
    }

    // Our API/storage convention is [lat, lng] (established before this map
    // library migration); GeoJSON/MapLibre require [lng, lat]. Convert only
    // at this boundary — the swap is its own inverse.
    function swap(pair) {
        return [pair[1], pair[0]];
    }

    let map = null;
    let draw = null;
    let currentPopup = null;
    let currentForm = null;
    let listContainer = null;
    let errorContainer = null;
    let isProcessing = false;
    let editingAnnotationId = null;
    let editShapeBar = null;
    const annotationsById = {};

    const POINTS_SOURCE = "annotation-points";
    const LINES_SOURCE = "annotation-lines";
    const POLYGONS_SOURCE = "annotation-polygons";
    const TEXT_FONT = ["Open Sans Semibold"];

    // Error display and feedback
    function showError(message, duration) {
        duration = duration || 5000;
        if (!errorContainer) return;
        const errorEl = document.createElement("div");
        errorEl.className = "error-message";
        errorEl.setAttribute("role", "alert");
        errorEl.textContent = message;
        errorContainer.appendChild(errorEl);
        setTimeout(function () { errorEl.remove(); }, duration);
    }

    function setProcessing(isActive) {
        isProcessing = isActive;
    }

    function isOperationInProgress() {
        return isProcessing;
    }

    function emptyFeatureCollection() {
        return { type: "FeatureCollection", features: [] };
    }

    function bboxOf(lngLatPairs) {
        let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
        lngLatPairs.forEach(function (pair) {
            if (pair[0] < minLng) minLng = pair[0];
            if (pair[1] < minLat) minLat = pair[1];
            if (pair[0] > maxLng) maxLng = pair[0];
            if (pair[1] > maxLat) maxLat = pair[1];
        });
        return [[minLng, minLat], [maxLng, maxLat]];
    }

    // ---------- Basemap + orthomosaic ----------

    function addBasemapAndOrthomosaic() {
        map.addSource("basemap-osm", {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            maxzoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        });
        map.addSource("basemap-esri", {
            type: "raster",
            tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
            attribution: "Tiles &copy; Esri",
        });
        map.addLayer({ id: "basemap-osm-layer", type: "raster", source: "basemap-osm" });
        map.addLayer({
            id: "basemap-esri-layer",
            type: "raster",
            source: "basemap-esri",
            layout: { visibility: "none" },
        });

        map.addSource("orthomosaic", {
            type: "raster",
            tiles: [tileUrl()],
            tileSize: 256,
            minzoom: config.minZoom,
            maxzoom: config.maxZoom,
            scheme: config.tms ? "tms" : "xyz",
        });
        map.addLayer({
            id: "orthomosaic-layer",
            type: "raster",
            source: "orthomosaic",
            paint: { "raster-opacity": 1 },
        });
    }

    function setBasemap(name) {
        map.setLayoutProperty("basemap-osm-layer", "visibility", name === "osm" ? "visible" : "none");
        map.setLayoutProperty("basemap-esri-layer", "visibility", name === "esri" ? "visible" : "none");
    }

    function addBasemapControl() {
        const control = {
            onAdd: function () {
                const container = document.createElement("div");
                container.className = "maplibregl-ctrl basemap-ctrl";

                const toggle = document.createElement("button");
                toggle.type = "button";
                toggle.className = "basemap-ctrl-toggle";
                toggle.title = "Basemap layers";
                toggle.setAttribute("aria-label", "Choose basemap layer");
                toggle.setAttribute("aria-expanded", "false");

                const list = document.createElement("div");
                list.className = "basemap-ctrl-list";
                list.setAttribute("role", "radiogroup");
                list.setAttribute("aria-label", "Basemap layer");

                const options = [
                    { value: "osm", label: "OpenStreetMap" },
                    { value: "esri", label: "Esri World Imagery" },
                    { value: "none", label: "No basemap" },
                ];
                options.forEach(function (opt, i) {
                    const optionLabel = document.createElement("label");
                    const radio = document.createElement("input");
                    radio.type = "radio";
                    radio.name = "basemap-layer";
                    radio.value = opt.value;
                    if (i === 0) radio.checked = true;
                    radio.addEventListener("change", function () {
                        setBasemap(opt.value);
                    });
                    optionLabel.appendChild(radio);
                    optionLabel.appendChild(document.createTextNode(" " + opt.label));
                    list.appendChild(optionLabel);
                });

                function collapse() {
                    container.classList.remove("basemap-ctrl-expanded");
                    toggle.setAttribute("aria-expanded", "false");
                }
                toggle.addEventListener("click", function () {
                    const expanded = container.classList.toggle("basemap-ctrl-expanded");
                    toggle.setAttribute("aria-expanded", String(expanded));
                });
                // Collapse on any click outside the control, same as Leaflet's
                // layers control on desktop.
                document.addEventListener("click", function (e) {
                    if (!container.contains(e.target)) collapse();
                });
                container.addEventListener("keydown", function (e) {
                    if (e.key === "Escape") collapse();
                });

                container.appendChild(toggle);
                container.appendChild(list);
                this._container = container;
                return container;
            },
            onRemove: function () {
                this._container.remove();
            },
        };
        map.addControl(control, "top-right");
    }

    function addOpacityControl() {
        const container = document.createElement("div");
        container.className = "map-ctrl-slider map-ctrl-slider-bottom-center";

        const label = document.createElement("label");
        label.textContent = "Orthomosaic opacity";
        label.htmlFor = "opacity-slider";
        container.appendChild(label);

        const input = document.createElement("input");
        input.id = "opacity-slider";
        input.type = "range";
        input.setAttribute("aria-label", "Adjust annotation opacity");
        input.setAttribute("aria-valuemin", "0");
        input.setAttribute("aria-valuemax", "100");
        input.setAttribute("aria-valuenow", "100");
        input.min = "0";
        input.max = "1";
        input.step = "0.05";
        input.value = "1";
        input.addEventListener("input", function () {
            map.setPaintProperty("orthomosaic-layer", "raster-opacity", parseFloat(input.value));
            input.setAttribute("aria-valuenow", Math.round(parseFloat(input.value) * 100));
        });
        container.appendChild(input);

        document.querySelector(".map-shell").appendChild(container);
    }

    // ---------- Annotation layers ----------

    function addAnnotationLayers() {
        map.addSource(POINTS_SOURCE, { type: "geojson", data: emptyFeatureCollection() });
        map.addSource(LINES_SOURCE, { type: "geojson", data: emptyFeatureCollection() });
        map.addSource(POLYGONS_SOURCE, { type: "geojson", data: emptyFeatureCollection() });

        map.addLayer({
            id: "annotation-polygons-fill",
            type: "fill",
            source: POLYGONS_SOURCE,
            paint: { "fill-color": mapColors.polygonFill, "fill-opacity": 0.15 },
        });
        map.addLayer({
            id: "annotation-polygons-outline",
            type: "line",
            source: POLYGONS_SOURCE,
            paint: { "line-color": mapColors.polygonFill, "line-width": 2 },
        });
        map.addLayer({
            id: "annotation-polygons-label",
            type: "symbol",
            source: POLYGONS_SOURCE,
            layout: { "text-field": ["get", "title"], "text-font": TEXT_FONT, "text-size": 13 },
            paint: { "text-color": mapColors.textColor, "text-halo-color": mapColors.textHalo, "text-halo-width": 1.5 },
        });

        map.addLayer({
            id: "annotation-lines-line",
            type: "line",
            source: LINES_SOURCE,
            paint: { "line-color": mapColors.line, "line-width": 3 },
        });
        /* symbol-placement: "line" is the whole point of this migration — MapLibre
           places (and re-places on zoom/pan) repeated labels along the actual line
           geometry, correctly oriented through bends, with no manual per-segment
           splitting or orientation math needed (contrast with the Leaflet.TextPath
           workarounds this replaces). */
        map.addLayer({
            id: "annotation-lines-label",
            type: "symbol",
            source: LINES_SOURCE,
            layout: {
                "text-field": ["get", "title"],
                "text-font": TEXT_FONT,
                "symbol-placement": "line",
                "symbol-spacing": 120,
                "text-size": 13,
                "text-rotation-alignment": "map",
            },
            paint: { "text-color": mapColors.textColor, "text-halo-color": mapColors.textHalo, "text-halo-width": 1.5 },
        });

        map.addLayer({
            id: "annotation-points-circle",
            type: "circle",
            source: POINTS_SOURCE,
            paint: {
                "circle-radius": 6,
                "circle-color": mapColors.point,
                "circle-stroke-width": 2,
                "circle-stroke-color": mapColors.textHalo,
            },
        });
        map.addLayer({
            id: "annotation-points-label",
            type: "symbol",
            source: POINTS_SOURCE,
            layout: {
                "text-field": ["get", "title"],
                "text-font": TEXT_FONT,
                "text-anchor": "left",
                "text-offset": [1, 0],
                "text-size": 13,
            },
            paint: { "text-color": mapColors.textColor, "text-halo-color": mapColors.textHalo, "text-halo-width": 1.5 },
        });
    }

    function annotationToFeature(annotation) {
        let geometry;
        if (annotation.kind === "line") {
            geometry = { type: "LineString", coordinates: annotation.path.map(swap) };
        } else if (annotation.kind === "polygon") {
            const ring = annotation.path.map(swap);
            geometry = { type: "Polygon", coordinates: [ring.concat([ring[0]])] };
        } else {
            geometry = { type: "Point", coordinates: swap([annotation.lat, annotation.lng]) };
        }
        return {
            type: "Feature",
            id: annotation.id,
            properties: { id: annotation.id, title: annotation.title },
            geometry: geometry,
        };
    }

    function refreshAnnotationSources() {
        const points = [], lines = [], polygons = [];
        Object.keys(annotationsById).forEach(function (id) {
            // Hidden from our own layers while its shape is being edited via
            // Mapbox GL Draw, so the two renderings don't sit on top of each other.
            if (editingAnnotationId != null && String(id) === String(editingAnnotationId)) return;
            const annotation = annotationsById[id];
            const feature = annotationToFeature(annotation);
            if (annotation.kind === "line") {
                lines.push(feature);
            } else if (annotation.kind === "polygon") {
                polygons.push(feature);
            } else {
                points.push(feature);
            }
        });
        map.getSource(POINTS_SOURCE).setData({ type: "FeatureCollection", features: points });
        map.getSource(LINES_SOURCE).setData({ type: "FeatureCollection", features: lines });
        map.getSource(POLYGONS_SOURCE).setData({ type: "FeatureCollection", features: polygons });
    }

    function focusOnAnnotation(annotation) {
        if (annotation.kind === "line" || annotation.kind === "polygon") {
            const bbox = bboxOf(annotation.path.map(swap));
            map.fitBounds(bbox, { maxZoom: config.maxZoom, padding: 60 });
        } else {
            map.flyTo({
                center: swap([annotation.lat, annotation.lng]),
                zoom: Math.max(map.getZoom(), config.maxZoom),
            });
        }
    }

    function wireAnnotationClicks() {
        const interactiveLayers = [
            "annotation-points-circle",
            "annotation-lines-line",
            "annotation-polygons-fill",
        ];
        interactiveLayers.forEach(function (layerId) {
            map.on("click", layerId, function (e) {
                const annotation = annotationsById[e.features[0].properties.id];
                if (!annotation) {
                    return;
                }
                focusOnAnnotation(annotation);
                showPopup(annotation, e.lngLat);
            });
            map.on("mouseenter", layerId, function () {
                map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", layerId, function () {
                map.getCanvas().style.cursor = "";
            });
        });
    }

    // ---------- Load / render / list ----------

    function loadAnnotations() {
        apiFetch(config.annotationsUrl)
            .then(function (annotations) {
                annotations.forEach(renderAnnotation);
            })
            .catch(function (error) {
                showError("Failed to load annotations: " + error.message);
            });
    }

    const KIND_ICON_CLASSES = { point: "bi-geo-alt-fill", line: "bi-rulers", polygon: "bi-hexagon-fill" };

    function setAnnotationLabel(label, annotation) {
        label.textContent = "";
        const icon = document.createElement("i");
        icon.className = "bi " + (KIND_ICON_CLASSES[annotation.kind] || KIND_ICON_CLASSES.point);
        icon.setAttribute("aria-hidden", "true");
        label.appendChild(icon);
        label.appendChild(document.createTextNode(" " + annotation.title));
    }

    function renderAnnotation(annotation) {
        annotationsById[annotation.id] = annotation;
        refreshAnnotationSources();
        addSidebarRow(annotation);
    }

    function removeAnnotation(id) {
        if (currentPopup) {
            currentPopup.remove();
            currentPopup = null;
        }
        delete annotationsById[id];
        refreshAnnotationSources();
        const row = listContainer && listContainer.querySelector('[data-annotation-id="' + id + '"]');
        if (row) {
            row.remove();
        }
    }

    function searchInputValue() {
        const input = document.getElementById("annotations-search");
        return input ? input.value : "";
    }

    function filterSidebarRows(query) {
        if (!listContainer) {
            return;
        }
        const needle = query.trim().toLowerCase();
        let visibleCount = 0;
        Array.prototype.forEach.call(listContainer.children, function (row) {
            if (row.classList.contains('no-results')) return;
            const match = !needle || (row.dataset.title || "").includes(needle);
            row.style.display = match ? "" : "none";
            if (match) visibleCount++;
        });
        
        // Show "no results" message if all filtered out
        let noResultsMsg = listContainer.parentElement.querySelector('.no-results');
        if (visibleCount === 0 && needle) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results';
                noResultsMsg.textContent = 'No annotations matching search';
                listContainer.parentElement.appendChild(noResultsMsg);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
    }

    function addSidebarRow(annotation) {
        if (!listContainer) {
            return;
        }
        const row = document.createElement("div");
        row.className = "annotation-list-row";
        row.dataset.annotationId = annotation.id;
        row.dataset.title = annotation.title.toLowerCase();

        const label = document.createElement("button");
        label.type = "button";
        label.className = "annotation-list-label";
        setAnnotationLabel(label, annotation);
        label.setAttribute("aria-label", "View " + annotation.title);
        label.addEventListener("click", function () {
            focusOnAnnotation(annotation);
        });
        row.appendChild(label);

        if (config.canEdit) {
            const deleteBtn = document.createElement("button");
            deleteBtn.type = "button";
            deleteBtn.className = "icon-btn";
            deleteBtn.title = "Delete";
            deleteBtn.setAttribute("aria-label", "Delete " + annotation.title);
            deleteBtn.innerHTML = '<i class="bi bi-trash" aria-hidden="true"></i>';
            deleteBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (isOperationInProgress()) return;
                if (confirm("Delete \"" + annotation.title + "\"? This cannot be undone.")) {
                    deleteBtn.disabled = true;
                    setProcessing(true);
                    apiFetch(annotationDetailUrl(annotation.id), { method: "DELETE" })
                        .then(function () {
                            removeAnnotation(annotation.id);
                        })
                        .catch(function (error) {
                            showError("Failed to delete annotation: " + error.message);
                            deleteBtn.disabled = false;
                        })
                        .finally(function () {
                            setProcessing(false);
                        });
                }
            });
            row.appendChild(deleteBtn);
        }

        listContainer.appendChild(row);
        filterSidebarRows(searchInputValue());
    }

    function updateSidebarRow(annotation) {
        if (!listContainer) {
            return;
        }
        const row = listContainer.querySelector('[data-annotation-id="' + annotation.id + '"]');
        if (!row) {
            return;
        }
        row.dataset.title = annotation.title.toLowerCase();
        const label = row.querySelector(".annotation-list-label");
        if (label) {
            setAnnotationLabel(label, annotation);
            label.setAttribute("aria-label", "View " + annotation.title);
        }
    }

    // ---------- Edit details (title/description) ----------

    function renderEditDetailsForm(annotation) {
        const container = document.createElement("div");
        container.className = "annotation-popup annotation-edit-form";

        const titleLabel = document.createElement("label");
        titleLabel.textContent = "Title";
        const titleInput = document.createElement("input");
        titleInput.type = "text";
        titleInput.value = annotation.title;
        titleInput.maxLength = 200;
        titleLabel.appendChild(titleInput);
        container.appendChild(titleLabel);

        const descLabel = document.createElement("label");
        descLabel.textContent = "Description";
        const descInput = document.createElement("textarea");
        descInput.value = annotation.description || "";
        descInput.maxLength = 1000;
        descLabel.appendChild(descInput);
        container.appendChild(descLabel);

        const actions = document.createElement("div");
        actions.className = "annotation-popup-actions";

        const saveBtn = document.createElement("button");
        saveBtn.type = "button";
        saveBtn.className = "btn btn-sm";
        saveBtn.textContent = "Save";
        saveBtn.addEventListener("click", function () {
            const title = titleInput.value.trim();
            const description = descInput.value.trim();
            if (!title) {
                showError("Title is required");
                return;
            }
            if (title.length > 200) {
                showError("Title must be 200 characters or less");
                return;
            }
            if (description.length > 1000) {
                showError("Description must be 1000 characters or less");
                return;
            }
            if (isOperationInProgress()) return;

            saveBtn.disabled = true;
            setProcessing(true);
            apiFetch(annotationDetailUrl(annotation.id), {
                method: "PATCH",
                body: JSON.stringify({ title: title, description: description }),
            })
                .then(function (updated) {
                    annotationsById[annotation.id] = updated;
                    refreshAnnotationSources();
                    updateSidebarRow(updated);
                    if (currentPopup) {
                        currentPopup.setDOMContent(renderPopupContent(updated));
                    }
                    showError("Annotation updated", 2000);
                })
                .catch(function (error) {
                    showError("Failed to update annotation: " + error.message);
                    saveBtn.disabled = false;
                })
                .finally(function () {
                    setProcessing(false);
                });
        });
        actions.appendChild(saveBtn);

        const cancelBtn = document.createElement("button");
        cancelBtn.type = "button";
        cancelBtn.className = "btn btn-sm btn-secondary";
        cancelBtn.textContent = "Cancel";
        cancelBtn.addEventListener("click", function () {
            if (currentPopup) {
                currentPopup.setDOMContent(renderPopupContent(annotation));
            }
        });
        actions.appendChild(cancelBtn);

        container.appendChild(actions);
        return container;
    }

    // ---------- Edit shape (reposition / reshape geometry) ----------

    function showEditShapeBar(annotation, onSave, onCancel) {
        hideEditShapeBar();
        const bar = document.createElement("div");
        bar.className = "edit-shape-bar";

        const label = document.createElement("span");
        label.textContent = annotation.kind === "point"
            ? "Drag the point to move it."
            : "Drag the points to reshape. Click a segment to add a point.";
        bar.appendChild(label);

        const saveBtn = document.createElement("button");
        saveBtn.type = "button";
        saveBtn.className = "btn btn-sm";
        saveBtn.textContent = "Save";
        saveBtn.addEventListener("click", onSave);
        bar.appendChild(saveBtn);

        const cancelBtn = document.createElement("button");
        cancelBtn.type = "button";
        cancelBtn.className = "btn btn-sm btn-secondary";
        cancelBtn.textContent = "Cancel";
        cancelBtn.addEventListener("click", onCancel);
        bar.appendChild(cancelBtn);

        // Same reasoning as the annotation-form overlay: without this, clicks
        // on these buttons also register as map clicks underneath.
        bar.addEventListener("click", function (e) { e.stopPropagation(); });
        bar.addEventListener("mousedown", function (e) { e.stopPropagation(); });

        document.getElementById("map").appendChild(bar);
        editShapeBar = bar;
    }

    function hideEditShapeBar() {
        if (editShapeBar) {
            editShapeBar.remove();
            editShapeBar = null;
        }
    }

    function cancelEditingShape() {
        if (editingAnnotationId == null) return;
        if (draw.get(editingAnnotationId)) {
            draw.delete(editingAnnotationId);
        }
        editingAnnotationId = null;
        refreshAnnotationSources();
        hideEditShapeBar();
        draw.changeMode("simple_select");
    }

    function saveEditedShape(annotation) {
        const feature = draw.get(editingAnnotationId);
        if (!feature) {
            cancelEditingShape();
            return;
        }
        const payload = {};
        if (annotation.kind === "point") {
            payload.lat = feature.geometry.coordinates[1];
            payload.lng = feature.geometry.coordinates[0];
        } else if (annotation.kind === "line") {
            payload.path = feature.geometry.coordinates.map(swap);
        } else {
            const ring = feature.geometry.coordinates[0].slice(0, -1); // drop closing duplicate
            payload.path = ring.map(swap);
        }

        if (isOperationInProgress()) return;
        setProcessing(true);
        apiFetch(annotationDetailUrl(annotation.id), {
            method: "PATCH",
            body: JSON.stringify(payload),
        })
            .then(function (updated) {
                annotationsById[annotation.id] = updated;
                draw.delete(editingAnnotationId);
                editingAnnotationId = null;
                refreshAnnotationSources();
                hideEditShapeBar();
                draw.changeMode("simple_select");
                showError("Shape updated", 2000);
            })
            .catch(function (error) {
                showError("Failed to update shape: " + error.message);
            })
            .finally(function () {
                setProcessing(false);
            });
    }

    function startEditingShape(annotation) {
        if (isOperationInProgress()) return;
        if (editingAnnotationId != null) {
            cancelEditingShape();
        }
        editingAnnotationId = annotation.id;
        refreshAnnotationSources();

        draw.add(annotationToFeature(annotation));
        if (annotation.kind === "point") {
            draw.changeMode("simple_select", { featureIds: [annotation.id] });
        } else {
            draw.changeMode("direct_select", { featureId: annotation.id });
        }

        showEditShapeBar(
            annotation,
            function () { saveEditedShape(annotation); },
            function () { cancelEditingShape(); }
        );
    }

    function renderPopupContent(annotation) {
        const container = document.createElement("div");
        container.className = "annotation-popup";

        const title = document.createElement("strong");
        title.className = "annotation-popup-title";
        title.textContent = annotation.title;
        container.appendChild(title);

        if (annotation.description) {
            const desc = document.createElement("p");
            desc.className = "annotation-popup-desc";
            desc.textContent = annotation.description;
            container.appendChild(desc);
        }

        if (config.canEdit) {
            const actions = document.createElement("div");
            actions.className = "annotation-popup-actions";

            const editBtn = document.createElement("button");
            editBtn.type = "button";
            editBtn.className = "btn btn-sm";
            editBtn.textContent = "Edit";
            editBtn.setAttribute("aria-label", "Edit annotation details");
            editBtn.addEventListener("click", function () {
                if (currentPopup) {
                    currentPopup.setDOMContent(renderEditDetailsForm(annotation));
                }
            });
            actions.appendChild(editBtn);

            const reshapeBtn = document.createElement("button");
            reshapeBtn.type = "button";
            reshapeBtn.className = "btn btn-sm";
            reshapeBtn.textContent = annotation.kind === "point" ? "Move" : "Reshape";
            reshapeBtn.setAttribute("aria-label", annotation.kind === "point" ? "Move point" : "Reshape " + annotation.kind);
            reshapeBtn.addEventListener("click", function () {
                if (currentPopup) {
                    currentPopup.remove();
                    currentPopup = null;
                }
                startEditingShape(annotation);
            });
            actions.appendChild(reshapeBtn);

            const deleteBtn = document.createElement("button");
            deleteBtn.textContent = "Delete";
            deleteBtn.type = "button";
            deleteBtn.className = "btn btn-sm danger";
            deleteBtn.setAttribute("aria-label", "Delete annotation");
            deleteBtn.addEventListener("click", function () {
                if (isOperationInProgress()) return;
                if (confirm("Delete \"" + annotation.title + "\"? This cannot be undone.")) {
                    deleteBtn.disabled = true;
                    setProcessing(true);
                    apiFetch(annotationDetailUrl(annotation.id), { method: "DELETE" })
                        .then(function () {
                            removeAnnotation(annotation.id);
                        })
                        .catch(function (error) {
                            showError("Failed to delete annotation: " + error.message);
                            deleteBtn.disabled = false;
                        })
                        .finally(function () {
                            setProcessing(false);
                        });
                }
            });
            actions.appendChild(deleteBtn);

            container.appendChild(actions);
        }

        return container;
    }

    function showPopup(annotation, lngLat) {
        if (currentPopup) {
            currentPopup.remove();
        }
        currentPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "280px" })
            .setLngLat(lngLat)
            .setDOMContent(renderPopupContent(annotation))
            .addTo(map);
    }

    // ---------- Create form ----------

    function closeAnnotationForm() {
        if (currentForm) {
            currentForm.remove();
            currentForm = null;
        }
    }

    function openAnnotationForm(geometry) {
        closeAnnotationForm();

        const anchorPoint = map.project(geometry.anchor);

        const form = document.createElement("form");
        form.className = "annotation-form";
        form.style.left = anchorPoint.x + "px";
        form.style.top = anchorPoint.y + "px";
        form.innerHTML =
            '<p><label>Title<br><input name="title" required maxlength="200"></label></p>' +
            '<p><label>Description<br><textarea name="description" maxlength="1000"></textarea></label></p>' +
            '<button type="submit" class="btn">Add</button> ' +
            '<button type="button" data-role="cancel" class="btn">Cancel</button>';

        const submitBtn = form.querySelector('button[type="submit"]');

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            if (isOperationInProgress()) return;
            
            const title = form.elements.title.value.trim();
            const description = form.elements.description.value.trim();
            
            if (!title) {
                showError("Title is required");
                return;
            }
            
            if (title.length > 200) {
                showError("Title must be 200 characters or less");
                return;
            }
            
            if (description.length > 1000) {
                showError("Description must be 1000 characters or less");
                return;
            }

            const payload = {
                kind: geometry.kind,
                title: title,
                description: description,
            };
            if (geometry.kind === "line" || geometry.kind === "polygon") {
                payload.path = geometry.path;
            } else {
                payload.lat = geometry.lat;
                payload.lng = geometry.lng;
            }
            
            submitBtn.disabled = true;
            setProcessing(true);
            
            apiFetch(config.annotationsUrl, {
                method: "POST",
                body: JSON.stringify(payload),
            })
                .then(function (annotation) {
                    renderAnnotation(annotation);
                    closeAnnotationForm();
                    showError("Annotation created", 2000);
                })
                .catch(function (error) {
                    showError("Failed to create annotation: " + error.message);
                    submitBtn.disabled = false;
                })
                .finally(function () {
                    setProcessing(false);
                });
        });

        form.querySelector('[data-role="cancel"]').addEventListener("click", function () {
            closeAnnotationForm();
        });

        // Prevent clicks/drags inside this overlay form from reaching the map
        // underneath (MapLibre's canvas listens on the container; without this
        // a click on the form would also register as a map click).
        form.addEventListener("click", function (e) { e.stopPropagation(); });
        form.addEventListener("mousedown", function (e) { e.stopPropagation(); });

        document.getElementById("map").appendChild(form);
        currentForm = form;
    }

    // ---------- Draw tool ----------

    // Rectangle isn't a distinct annotation kind in our data model (it's just
    // a 4-point polygon), and Mapbox GL Draw has no dedicated rectangle-drag
    // mode — draw one as a polygon instead.

    // Mouse-following instructional tooltip, styled and worded after the
    // Leaflet Draw plugin's ".leaflet-draw-tooltip" (e.g. "Click to start
    // drawing a line."). Mapbox GL Draw has no built-in equivalent.
    const DRAW_TOOLTIP_TEXT = {
        draw_point: function () {
            return "Click map to place point.";
        },
        draw_line_string: function (n) {
            return n === 0 ? "Click to start drawing a line." : "Click to continue drawing a line.<br>Double-click to finish.";
        },
        draw_polygon: function (n) {
            if (n === 0) return "Click to start drawing a shape.";
            if (n < 3) return "Click to continue drawing a shape.";
            return "Click first point to close this shape.";
        },
    };

    function initDrawTooltip(map, draw) {
        let clickCount = 0;
        const tooltipEl = document.createElement("div");
        tooltipEl.className = "draw-tooltip";
        tooltipEl.style.display = "none";
        map.getContainer().appendChild(tooltipEl);

        function update(mode) {
            const textFor = DRAW_TOOLTIP_TEXT[mode];
            if (!textFor) {
                tooltipEl.style.display = "none";
                return;
            }
            tooltipEl.innerHTML = textFor(clickCount);
            tooltipEl.style.display = "block";
        }

        map.on("draw.modechange", function (e) {
            clickCount = 0;
            update(e.mode);
        });
        map.on("mousemove", function (e) {
            if (tooltipEl.style.display === "none") return;
            tooltipEl.style.left = e.point.x + "px";
            tooltipEl.style.top = e.point.y + "px";
        });
        map.on("click", function () {
            const mode = draw.getMode();
            if (mode === "draw_line_string" || mode === "draw_polygon") {
                clickCount++;
                update(mode);
            }
        });
    }

    function initDrawTool() {
        draw = new MapboxDraw({
            displayControlsDefault: false,
            controls: { point: true, line_string: true, polygon: true },
        });
        map.addControl(draw, "top-right");
        initDrawTooltip(map, draw);

        // Starting a fresh draw while an existing annotation's shape is mid-edit
        // would otherwise orphan that edit's temp feature in the Draw store.
        map.on("draw.modechange", function (e) {
            if (editingAnnotationId != null && e.mode !== "direct_select" && e.mode !== "simple_select") {
                cancelEditingShape();
            }
        });

        map.on("draw.create", function (e) {
            const feature = e.features[0];
            const geomType = feature.geometry.type;
            draw.delete(feature.id); // we render our own styled version once saved

            let geometry;
            if (geomType === "Point") {
                const coords = feature.geometry.coordinates;
                geometry = { kind: "point", lat: coords[1], lng: coords[0], anchor: { lng: coords[0], lat: coords[1] } };
            } else if (geomType === "LineString") {
                const coords = feature.geometry.coordinates;
                const last = coords[coords.length - 1];
                geometry = { kind: "line", path: coords.map(swap), anchor: { lng: last[0], lat: last[1] } };
            } else if (geomType === "Polygon") {
                const ring = feature.geometry.coordinates[0].slice(0, -1); // drop closing duplicate
                geometry = { kind: "polygon", path: ring.map(swap), anchor: { lng: ring[0][0], lat: ring[0][1] } };
            } else {
                return;
            }
            openAnnotationForm(geometry);
        });
    }

    // ---------- Init ----------

    function initMap() {
        errorContainer = document.getElementById("error-container");
        
        map = new maplibregl.Map({
            container: "map",
            style: {
                version: 8,
                glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
                sources: {},
                layers: [],
            },
            center: swap([config.centerLat || 0, config.centerLng || 0]),
            zoom: (config.minZoom || 2) + 1,
            minZoom: config.minZoom,
            maxZoom: config.maxZoom,
        });

        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
        map.addControl(new maplibregl.FullscreenControl(), "top-right");

        map.on("load", function () {
            addBasemapAndOrthomosaic();
            addAnnotationLayers();
            addBasemapControl();
            addOpacityControl();
            if (config.canEdit) {
                initDrawTool();
            }
            wireAnnotationClicks();

            listContainer = document.getElementById("annotations-list");
            const searchInput = document.getElementById("annotations-search");
            if (searchInput) {
                searchInput.addEventListener("input", function () {
                    filterSidebarRows(searchInput.value);
                });
            }
            loadAnnotations();
        });
    }

    initMap();
})();
