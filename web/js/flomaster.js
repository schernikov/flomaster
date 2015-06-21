$(window).load(function(){

	var btnsgrp = $("#flobtns");
	var areagrp = $("#areabtns");
	var relayswitches = [];
	function btnmaker(idx) {
		var btn = $("<button>").addClass("btn btn-primary");
		btn.append(idx);
		btn.click(function() {
			if(!btn.hasClass('active')){ /* inverse state here */
				connection.sendmsg({'relay':idx, 'state':'on'});
			} else {
				connection.sendmsg({'relay':idx, 'state':'off'});
			}
		});
		return btn;
	}

	var active_area = null;
	var areas = {};
	function switch_area(btn, active) {
		if(!btn.hasClass('active')){ /* inverse state here */
			if (active_area != btn) {
				if (active_area) { 
					active_area.removeClass('active');
				}
				active_area = btn;
			}
		} else {
			if (active_area && active_area[0] == btn[0]) {
				active_area = null;
			}
		}
	}
	function areamaker(nm, idx) {
		var btn = $("<button>").addClass("btn btn-primary");
		btn.append(nm);
		btn.click(function() {
			var active = !btn.hasClass('active'); /* inverse state here */
			switch_area(btn, active);
			connection.sendmsg({'area':idx, 'state':(active?'on':'off')});
		});
		areas[idx] = btn;
		return btn;
	}	
	
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
			if(self.poller) clearInterval(self.poller);
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
	
	function onspeed(speed, stamp, ticks) {
		if(!params.init){
			params.oninit(stamp);
		}		
		data.push(speed);
		stamps.push(stamp);
		plotter.onstats(ticks);
	};

	var connection = new flowtools.Connection('/websocket', 
			{'flow':function(msg) {
						if(msg.counts){
							onspeed(msg.counts.speed, msg.counts.stamp, tickscount+msg.counts.ticks);
						} else if (msg.stop) {
							tickscount += msg.stop.ticks;
							onspeed(0, msg.stop.stamp, tickscount);
							console.log("stop: "+new Date().toString())
						} else if(msg.start) {
							stamp = msg.start.stamp;
							onspeed(0, msg.start.stamp, tickscount);
							params.onstart();
						} else {
							console.log("flow got: '"+msg.toString()+"'");
						}
					},
			'event':function(msg){
						if(msg.init){
							if(!msg.init.relays || !msg.init.relays.length){
								console.log("event: no initial relays info");
							} else {
								relayswitches = [];
								btnsgrp.empty();
								_.each(msg.init.relays, function(rel, idx) {
									var btn = btnmaker(idx+1);
									relayswitches.push(btn);
									btnsgrp.append(btn);
									if(rel == 'on') btn.addClass('active');
								});
							}
							areagrp.empty();
							_.each(msg.init.areas, function(area, idx) {
								var btn = areamaker(area[1], area[0]);
								areagrp.append(btn);
							});
							var mast = msg.init.master;
							if ((parseInt(mast) === mast) && 
								mast > 0 && mast <= relayswitches.length) {
								console.log("master "+mast);
							}
							
						} else if(msg.update) {
							if(!(msg.update.relay || msg.update.area) || !msg.update.state){
								console.log("event: bad update info: "+msg.update.toString());
							} else {
								if (msg.update.relay) {
									var idx = msg.update.relay-1;
									if(idx >= relayswitches.length || idx < 0){
										console.log("event: invalid relay: "+msg.update.toString());
									} else {
										if(msg.update.state == 'on'){
											relayswitches[idx].addClass('active');
										} else {
											relayswitches[idx].removeClass('active');
										}
									}
								}
								if (msg.update.area) {
									var btn = areas[msg.update.area];
									if (btn) {
										var isOn = (msg.update.state == 'on');
										switch_area(btn, isOn);
										if (isOn) {
											btn.addClass('active');
										} else {
											btn.removeClass('active');
										}
									}
								}
							}
						} else {
							console.log("event got: '"+msg.toString()+"'");
						}
					}
			}
	);
	
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
		stats.append((count*0.003355).toFixed(2)+' литров');
	}
}
