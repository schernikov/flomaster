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
		if(active){
			if (!active_area || active_area[0] != btn[0]) {
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
	
	var /*data = [], stamps = [], */offset = 0, tickscount = 0;
	
/*	var params = {
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
*/
	var plotter = new Plotter();	
	
	function onspeed(speed, stamp, liters) {
		plotter.onstats(stamp, speed, liters);
	};

	var connection = new flowtools.Connection('/websocket', 
			{'flow':function(msg) {
						if(msg.counts){
							onspeed(msg.counts.speed, msg.counts.stamp, tickscount+msg.counts.liters);
						} else if (msg.stop) {
							tickscount += msg.stop.liters;
							onspeed(0, msg.stop.stamp, tickscount);
						} else if(msg.start) {
							stamp = msg.start.stamp;
							onspeed(0, msg.start.stamp, tickscount);
							plotter.start();
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
});

function Plotter(/*params*/) {
	var self = this;
	var live = $('#liveflow');
	
	var smoothie = new SmoothieChart({millisPerPixel:30, 
		grid:{fillStyle:'#ffffff',strokeStyle:'rgba(119,119,119,0.34)',borderVisible:false,
			  verticalSections:0,
			  millisPerLine:5000},
		maxValueScale:1.2,
		labels:{fillStyle:'rgba(99,99,99,0.78)'},
		minValue:0/*,
		timestampFormatter:SmoothieChart.timeFormatter*/});
	
	var series = new TimeSeries();
	smoothie.addTimeSeries(series, {lineWidth:2,strokeStyle:'#00ff00',fillStyle:'rgba(0,0,0,0.30)'});
	smoothie.streamTo(document.getElementById("liveflow"), 2000);
	
	var stats = $('<div>').addClass('flostats');
	$('#live-placeholder').append(stats);

	self.onstats = function(stamp, speed, liters) {
		stats.empty();
		stats.append(liters.toFixed(2)+' литров');
		series.append(stamp*1000, speed);
	}
	
	self.start = function() {
		//smoothie.start();
	}
}
