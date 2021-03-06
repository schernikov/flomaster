flowtools = {
	SessionControl: function (sendmsg, start, stop) {
			var self = this;
			var init = null;
			var sleeper = null;
			var startstamp = null;
			var starter = null;
			var startgap = 0;
			var pinger = null;
			var ponger = null;
			
			self.onmessage = function(msg) {
				if(msg.init){
					init = msg.init;
					if(init == null){
						oninit();
					}
				}
				if(msg === 'pong'){
					stoppong();
				}
				if(msg === 'ping'){
					sendmsg('pong');
				}
			}
			function doping() {
				stoppong();
				sendmsg('ping');
				ponger = setTimeout(function() {
					stop(); /* no pong - socket is dead */
				}, init.pingtimeout);
			}
			function startping() {
				if(!init) return null;
				return setInterval(function() {
					doping();
				}, init.poll);
			}
			function stopping() {
				stoppong();
				clearTimeout(pinger);
				pinger = null;
			}
			function stoppong() {
				clearTimeout(ponger);
				ponger = null;
			}
			function startup(gap) {
				clearTimeout(starter);
				startstamp = new Date();
				starter = setTimeout(function() {
					start();
					pinger = startping();
				}, gap);
			}
			self.onclose = function() {
				stopping();
				if(!init) return; /* it was not initialized */
				var now = new Date();
				var diff = now-startstamp;
				if(diff < init.span){	/* is it too often? */
					if(startgap == 0){
						startgap = 100;
					} else {
						if(startgap < init.span){
							startgap = startgap*2;
						}
					}
				} else {
					if(diff > init.longspan){
						startgap = 0;
					}
				}
				startup(startgap);
			}
			
			self.terminate = function() {
				stop();
			}
			
			function oninit() {
				var lastcheck = new Date();
		
				setInterval(function() {
					var now = new Date();
					if((now - lastcheck) > init.period){
						doping(); /* let's check socket by ping */
					}
					lastcheck = now;
				}, init.sleeper);
		
				pinger = startping();
			}
			startup(0);
		},
		
	openChannel: function (url, callback, onopen, onclose) {
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
	},
	Connection: function(wsurl, msgmap) {
		var self = this;
		var socket = null, session = null;

		msgmap['session'] = function(cont) {
			session.onmessage(cont);
		};
		
		function onmessage(message) {
			if(!message){
				console.log("ws: empty message?!");
				return;
			}
			var msg = jQuery.parseJSON(message);
			if(msg.type && msgmap[msg.type]){
				msgmap[msg.type](msg.cont);
			} else {
				console.log("ws got: '"+message+"'");
			}
		}
		function onopen(s) {
			socket = s;
		}
		function onclose(s) {
			socket = null;
			session.onclose();
		}
		function send(message) {
			if (!socket) return;
			var msgString = JSON.stringify(message);
			console.log(new Date().toString()+': '+msgString);
			socket.send(msgString);
		}
		
		self.sendmsg = function (message) {
			send({'type':'event', 'cont':message});
		}
		session = new flowtools.SessionControl(function(msg) {
			send({'type':'session', 'cont':msg});
		}, function() {
			flowtools.openChannel(wsurl, onmessage, onopen, onclose);
		}, function() {
			if(socket) socket.close();
		});
		
		window.onbeforeunload = function() {
			session.terminate();
		}
	}
};
