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
	
	var data = [0], totalPoints = 300;
	
	function oncounts(args) {
		if(data.length > totalPoints){
			data = data.slice(1);
		}
		data.push(args.speed);
		console.log('speed:'+args.speed);
		
		update();
	};
	function onmessage(message) {
		if(!message){
			console.log("ws: empty message?!");
			return;
		}
		var msg = jQuery.parseJSON(message);
		if(msg.counts){
			oncounts(msg.counts);
		} else {
			console.log("ws got: '"+message+"'");
		}
	}
	function onopen(s) {
		console.log("opening ws");
	}
	function onclose(s) {
		console.log("closing ws");
	}
	openChannel('/websocket', onmessage, onopen, onclose);
	

	function getData() {
		var res = [];
		for (var i = 0; i < data.length; ++i) {
			res.push([i, data[i]])
		}
		return res;
	}

	var plot = $.plot("#placeholder", [ getData() ], {
		series: {
			shadowSize: 0	// Drawing is faster without shadows
		},
		yaxis: {
			min: 0,
			max: 500
		},
		xaxis: {
			min: 0,
			max: totalPoints,
			//show: false
		}
	});

	function update() {
		plot.setData([getData()]);

		// Since the axes don't change, we don't need to call plot.setupGrid()

		plot.draw();
	}

	update();
});
