$(window).load(function(){
	function openChannel(url, callback, onopen, onclose) {
		console.log("Opening channel.");
		var origin = window.location.hostname;
		if (window.location.port != "") {
			origin += ":" + window.location.port;
		}
		var pref = (window.location.protocol == 'http:') ? 'ws:' : 'wss:';
		var wsurl = pref + "//" + origin + url;
		var socket = new WebSocket(wsurl);
		socket.onopen = function() {
			console.log('Channel opened.');
			onopen(socket);
		};
		socket.onmessage = function(evt) {
			callback(evt.data);
		};
		socket.onerror = function(evt) {
			console.log('Channel error.');
			onclose(socket);
		};
		socket.onclose = function(evt) {
			console.log('Channel closed.');
			onclose(socket);
		};
	}

	function onmessage(message) {
		console.log("ws got: '"+message+"'");
	}
	function onopen(s) {
		console.log("opening ws");
	}
	function onclose(s) {
		console.log("closing ws");
	}
	openChannel('/websocket', onmessage, onopen, onclose);
	
	var data = [],
		totalPoints = 300;

	function getRandomData() {

		if (data.length > 0)
			data = data.slice(1);

		// Do a random walk

		while (data.length < totalPoints) {

			var prev = data.length > 0 ? data[data.length - 1] : 50,
				y = prev + Math.random() * 10 - 5;

			if (y < 0) {
				y = 0;
			} else if (y > 100) {
				y = 100;
			}

			data.push(y);
		}

		// Zip the generated y values with the x values

		var res = [];
		for (var i = 0; i < data.length; ++i) {
			res.push([i, data[i]])
		}

		return res;
	}

	// Set up the control widget

	var updateInterval = 30;
	$("#updateInterval").val(updateInterval).change(function () {
		var v = $(this).val();
		if (v && !isNaN(+v)) {
			updateInterval = +v;
			if (updateInterval < 1) {
				updateInterval = 1;
			} else if (updateInterval > 2000) {
				updateInterval = 2000;
			}
			$(this).val("" + updateInterval);
		}
	});

	var plot = $.plot("#placeholder", [ getRandomData() ], {
		series: {
			shadowSize: 0	// Drawing is faster without shadows
		},
		yaxis: {
			min: 0,
			max: 100
		},
		xaxis: {
			show: false
		}
	});

	function update() {

		plot.setData([getRandomData()]);

		// Since the axes don't change, we don't need to call plot.setupGrid()

		plot.draw();
		setTimeout(update, updateInterval);
	}

	update();
});
