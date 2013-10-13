$(window).load(function(){

	var data = [], stamps = [], offset = 0, tickscount = 0;
	
	var params = {
		init: false,
		top: 300,
		window: 30, // seconds
		tick: 50, // milliseconds
		
		started: false,
		oninit: function(stamp) {
			var self = this;
			self.init = true;
			self.startstamp = stamp;
			self.starttime = new Date().getTime();
			offset = stamp;
			self.onstart();
		},
		onstart: function() {
			var self = this;
			self.poller = setInterval(function() {
				self.onpoll();
			}, self.tick);
		}, 
		onpoll: function(first) {
			var self = this;
			var now = new Date().getTime();
			var cutoff = self.startstamp+(now-self.starttime)/1000-self.window;
			var vals = getData(cutoff);
			if(vals[vals.length-1][1] == 0){  			   // last value is 0
				if(vals.length == 1 && self.started){
					clearInterval(self.poller);
					self.started = false;
				}
				if(vals.length < 2 || vals[vals.length-2][1] != 0){
					vals.push([self.window, 0]);		   // add one more point to draw horizontal line at 0
				} else {
					vals[vals.length-1][0] = self.window;  // always keep zero line end at window border
				}
			} else {
				self.started = true;
			}
			plotter.show(vals);
		},
	};

	var plotter = new Plotter(params);	
	
	function onspeed(speed, stamp) {
		data.push(speed);
		stamps.push(stamp);
	};
	function onmessage(message) {
		if(!message){
			console.log("ws: empty message?!");
			return;
		}
		var msg = jQuery.parseJSON(message);
		if(msg.counts){
			onspeed(msg.counts.speed, msg.counts.stamp);
			plotter.onstats(tickscount+msg.counts.ticks);
		} else if (msg.stop) {
			onspeed(0, msg.stop.stamp);
			console.log("stop: "+new Date().toString())
			tickscount += msg.stop.ticks;
			plotter.onstats(tickscount);
		} else if(msg.start) {
			onspeed(0, msg.start.stamp);
			if(!params.init){
				params.oninit(msg.start.stamp);
			} else {
				params.onstart();
			}
		} else {
			console.log("ws got: '"+message+"'");
		}
	}
	
	function onopen(s) {
		console.log("opening ws "+new Date().toString());
	}
	function onclose(s) {
		console.log("closing ws "+new Date().toString());
		
	}
	flowtools.openChannel('/websocket', onmessage, onopen, onclose);
	
	function getData(cutoff) {
		var res = [];
		if(stamps.length > 1){
			var last = stamps.length-1;
			for (var i = 1; i < stamps.length; ++i) {
				if(stamps[i] > cutoff){
					last = i-1;
					break;
				}
			}
			if(last > 0){
				data = data.slice(last);
				stamps = stamps.slice(last);
			}
		}
		for (var i = 0; i < data.length; ++i) {
			res.push([(stamps[i]-cutoff), data[i]])
		}
		return res;
	}
});

function Plotter(params) {
	var self = this;
	var place = $('#placeholder');
	
	var plot = $.plot(place, [ [[0, 0]] ], {
		series: {
			shadowSize: 0	// Drawing is faster without shadows
		},
		yaxis: {
			min: 0,
			max: params.top,
		},
		xaxis: {
			min: 0,
			max: params.window,
			//show: false
		}
	});

	self.show = function(vals) {
		plot.setData([vals]);

		// Since the axes don't change, we don't need to call plot.setupGrid()

		plot.draw();
	};
	var stats = $('<div>').addClass('flostats'); 
	place.append(stats);
	self.onstats = function(count) {
		stats.empty();
		stats.append(count);
	}
}
