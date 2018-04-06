initialize();

function initialize() {

    defaultLatLong = {
        lat: 45.9294795,
        lng: 15.9670753
    };

    var map = new google.maps.Map(document.getElementById('map'), {
        center: defaultLatLong,
        zoom: 4,
        mapTypeId: 'roadmap'
    });

    var input = document.getElementById('pac-input');

    var autocomplete = new google.maps.places.Autocomplete(input);

    autocomplete.bindTo('bounds', map);
    map.controls[google.maps.ControlPosition.TOP_LEFT].push(input);

    var marker = new google.maps.Marker({
        map: map,
        position: defaultLatLong,
        draggable: true,
        clickable: true
    });

    google.maps.event.addListener(marker, 'dragend', function (marker) {
        var latLng = marker.latLng;
        currentLatitude = latLng.lat();
        currentLongitude = latLng.lng();

        var latlng = {
            lat: currentLatitude,
            lng: currentLongitude
        };

        // https://developers.google.com/maps/documentation/geocoding/intro
        var geocoder = new google.maps.Geocoder;
        geocoder.geocode({
            'location': latlng
        }, function (results, status) {
            if (status === 'OK') {
                if (results[0]) {
                    input.value = results[0].formatted_address;

                    // passing data to Flask - START
                    var geodata = results;

                    $.ajax({
                        url: Flask.url_for('get_geodata_from_gm'),
                        data: JSON.stringify(geodata, null, '\t'),
                        contentType: 'application/json;charset=UTF-8',
                        type: 'POST',
                        success: function(response) {
                            console.log(response);
                        },
                        error: function(error) {
                            console.log(error);
                        }
                    });
                    // passing data to Flask - END

                } else {
                    window.alert('No results found');
                }
            } else {
                window.alert('Geocoder failed due to: ' + status);
            }
        });
    });

    autocomplete.addListener('place_changed', function () {
        var place = autocomplete.getPlace();
        if (!place.geometry) {
            return;
        }
        if (place.geometry.viewport) {
            map.fitBounds(place.geometry.viewport);
        } else {
            map.setCenter(place.geometry.location);
        }

        marker.setPosition(place.geometry.location);

        currentLatitude = place.geometry.location.lat();
        currentLongitude = place.geometry.location.lng();

        // passing data to Flask - START
        var latlng = {
            lat: currentLatitude,
            lng: currentLongitude
        };

        // https://developers.google.com/maps/documentation/geocoding/intro
        var geocoder = new google.maps.Geocoder;
        geocoder.geocode({
            'location': latlng
        }, function (results, status) {
            if (status === 'OK') {
                if (results[0]) {
                    input.value = results[0].formatted_address;

                    // passing data to Flask - START
                    var geodata = results;

                    $.ajax({
                        url: Flask.url_for('get_geodata_from_gm'),
                        data: JSON.stringify(geodata, null, '\t'),
                        contentType: 'application/json;charset=UTF-8',
                        type: 'POST',
                        success: function(response) {
                            console.log(response);
                        },
                        error: function(error) {
                            console.log(error);
                        }
                    });
                    // passing data to Flask - END

                } else {
                    window.alert('No results found');
                }
            } else {
                window.alert('Geocoder failed due to: ' + status);
            }
        });
        // passing data to Flask - END

    });
}