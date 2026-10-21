'use strict';
'require view';
'require fs';
'require poll';
'require dom';

// Renders the output of `nss-status -j` (the single source of truth for
// NSS plane health); this view only formats, it computes nothing itself.

function getStatus() {
	return fs.exec('/usr/sbin/nss-status', ['-j']).then(function(res) {
		if (res.code !== 0)
			throw new Error(res.stderr || 'nss-status failed');
		return JSON.parse(res.stdout);
	});
}

function stateBadge(state) {
	var map = {
		active:  ['#2e7d32', _('Offload active')],
		stalled: ['#c62828', _('NSS firmware heartbeat is silent; check the system log')],
		host:    ['#f9a825', _('Host stack (NSS plane not armed)')]
	};
	var m = map[state] || ['#757575', state];
	return E('div', {
		'style': 'display:inline-block;padding:.3em .8em;border-radius:.3em;color:#fff;font-weight:bold;background:' + m[0]
	}, [ m[1] ]);
}

// Every value below is device-derived (firmware version strings, netdev
// names, counters). LuCI's E() assigns a bare string to innerHTML and only
// builds text nodes for array members, so the brackets are load-bearing.
function row(label, value) {
	return E('tr', { 'class': 'tr' }, [
		E('td', { 'class': 'td left', 'style': 'min-width:30%' }, label),
		E('td', { 'class': 'td left' }, Array.isArray(value) ? value : [ value ])
	]);
}

function onoff(v) {
	return v ? _('loaded') : _('not loaded');
}

function offl(pkts, pct) {
	return String(pkts) + ' (' + pct + '%)';
}

function renderStatus(d) {
	var cores = (d.cores || []).map(function(c) {
		return 'core' + c.core + ' ' + c.avg + '%';
	}).join(', ');

	var igs = (d.sqm.igs || []).map(function(i) {
		return i.port + (i.active ? ' ✓' : ' ✗');
	}).join('  ');

	// d.mesh: {configured, fw_capable} - whether a mesh interface is set up
	// and whether the loaded firmware offloads 802.11s mesh.
	var mesh = d.mesh || {};
	var wifi = d.wifi_offload == 1 ?
	               (mesh.configured ? _('NSS offload active (wifili, 802.11s mesh offloaded)')
	                                : _('NSS offload active (wifili)')) :
	           d.wifi_offload == 0 ?
	               (mesh.configured && mesh.fw_capable ? _('host mode (mesh configured; firmware supports mesh offload)') :
	                mesh.configured ? _('host mode (mesh configured; this NSS firmware has no mesh offload)') :
	                                  _('host mode')) :
	           _('ath11k not loaded');

	// data-title lets the theme stack table rows into labeled cards on
	// narrow (mobile) screens.
	var portRows = (d.ports || []).map(function(p) {
		return E('tr', { 'class': 'tr' }, [
			E('td', { 'class': 'td', 'data-title': _('Port') }, [ p.netdev ]),
			E('td', { 'class': 'td', 'data-title': 'if_num' }, [ String(p.ifnum) ]),
			E('td', { 'class': 'td', 'data-title': _('Started') }, [ p.started ? _('yes') : _('no') ]),
			E('td', { 'class': 'td', 'data-title': _('TX offloaded') }, [ offl(p.tx_offloaded, p.tx_offload_pct) ]),
			E('td', { 'class': 'td', 'data-title': _('TX via host') }, [ String(p.tx_host_pkts) ]),
			E('td', { 'class': 'td', 'data-title': _('RX offloaded') }, [ offl(p.rx_offloaded, p.rx_offload_pct) ]),
			E('td', { 'class': 'td', 'data-title': _('RX to host') }, [ String(p.rx_host_pkts) ])
		]);
	});

	// ipq50xx with the switch on DSA: the firmware has one VLAN node per
	// standalone switch port and per bridge (per VLAN on a VLAN-aware bridge),
	// carried inside the GMAC above. A bridge's ports share its node, so the
	// nodes are listed by bridge and the ports' wire totals in a table of
	// their own: the glue has no per-port exception counters there.
	var dsaNodeRows = (d.dsa_nodes || []).map(function(n) {
		return E('tr', { 'class': 'tr' }, [
			E('td', { 'class': 'td', 'data-title': _('Node') }, [ n.name ]),
			E('td', { 'class': 'td', 'data-title': 'if_num' }, [ String(n.ifnum) ]),
			E('td', { 'class': 'td', 'data-title': 'VID' }, [ String(n.vid) ]),
			E('td', { 'class': 'td', 'data-title': _('Switch ports') }, [ (n.ports || []).join(' ') ])
		]);
	});
	var dsaPortRows = (d.dsa_ports || []).map(function(p) {
		return E('tr', { 'class': 'tr' }, [
			E('td', { 'class': 'td', 'data-title': _('Port') }, [ p.netdev ]),
			E('td', { 'class': 'td', 'data-title': _('Link') }, [ p.carrier ? _('up') : _('down') ]),
			E('td', { 'class': 'td', 'data-title': _('TX packets') }, [ String(p.tx_total) ]),
			E('td', { 'class': 'td', 'data-title': _('RX packets') }, [ String(p.rx_total) ])
		]);
	});

	var dsaSection = dsaNodeRows.length ? [
		E('h3', {}, _('Switch ports and bridges on the firmware (DSA)')),
		E('table', { 'class': 'table' }, [
			E('tr', { 'class': 'tr table-titles' }, [
				E('th', { 'class': 'th' }, _('Node')),
				E('th', { 'class': 'th' }, 'if_num'),
				E('th', { 'class': 'th' }, 'VID'),
				E('th', { 'class': 'th' }, _('Switch ports'))
			])
		].concat(dsaNodeRows)),
		E('p', {}, E('em', {}, _('Each standalone switch port reaches the firmware as its own VLAN node on the GMAC above. A bridge has one node that all its switch ports share, and a VLAN-aware bridge has one for each of its VLANs.'))),
		E('table', { 'class': 'table' }, [
			E('tr', { 'class': 'tr table-titles' }, [
				E('th', { 'class': 'th' }, _('Port')),
				E('th', { 'class': 'th' }, _('Link')),
				E('th', { 'class': 'th' }, _('TX packets')),
				E('th', { 'class': 'th' }, _('RX packets'))
			])
		].concat(dsaPortRows)),
		E('p', {}, E('em', {}, _('The offloaded share is part of the GMAC\'s figures above; the totals here are each port\'s own switch counters, all its VLANs together.')))
	] : [];

	return E('div', {}, [
		E('p', {}, stateBadge(d.state)),
		E('table', { 'class': 'table' }, [
			row(_('Firmware'), d.fw_version + ' (fw_mask ' + d.fw_mask + ')'),
			row(_('Heartbeat'), _('%s pkts/s (NSS→host)').format(d.heartbeat_pps)),
			row(_('NSS core load'), cores || '-'),
			row(_('ECM accelerated connections'), d.ecm.loaded
				? _('%s IPv4 / %s IPv6 / %s multicast').format(d.ecm.ipv4_accel, d.ecm.ipv6_accel, d.ecm.multicast_accel)
				: _('ECM not loaded')),
			row(_('Bridge offload'), d.glue === 'dwmac' && (d.dsa_nodes || []).length
				? _('Active through DSA VLAN nodes') : onoff(d.modules.bridge_mgr)),
			row(_('PPPoE manager'), onoff(d.modules.pppoe)),
			row(_('Wi-Fi data path'), wifi),
			row(_('SQM shaper'), d.sqm.active
				? (d.sqm.lanes
					? _('nsstbl on %s (a lane on the switch conduit %s)').format(d.sqm.device, d.sqm.shaping_device)
					: _('nsstbl on %s').format(d.sqm.device)) +
					(igs ? ' — ' + _('upload IGS: %s').format(igs) : '')
				: !d.sqm.enabled
					? _('off (no queue enabled in /etc/config/sqm)')
					: (d.sqm.device ? _('no NSS shaper on %s').format(d.sqm.device) : _('no NSS shaper'))),
			(d.sqm.fastlane && d.sqm.fastlane.active)
				? row(_('Fast lane'), _('egress %s pkts / ingress %s pkts — %s marking rules').format(
					d.sqm.fastlane.egress_pkts, d.sqm.fastlane.ingress_pkts, d.sqm.qos_marking_rules || 0))
				: E('tr', { 'style': 'display:none' })
		]),
		E('h3', {}, _('Firmware-attached ports')),
		E('table', { 'class': 'table' }, [
			E('tr', { 'class': 'tr table-titles' }, [
				E('th', { 'class': 'th' }, _('Port')),
				E('th', { 'class': 'th' }, 'if_num'),
				E('th', { 'class': 'th' }, _('Started')),
				E('th', { 'class': 'th' }, _('TX offloaded')),
				E('th', { 'class': 'th' }, _('TX via host')),
				E('th', { 'class': 'th' }, _('RX offloaded')),
				E('th', { 'class': 'th' }, _('RX to host'))
			])
		].concat(portRows.length ? portRows : [
			E('tr', { 'class': 'tr' }, [
				E('td', { 'class': 'td', 'colspan': '7' }, _('No ports attached — host stack'))
			])
		])),
		E('p', {}, E('em', {}, _('Offloaded packets are forwarded by the firmware and never reach the host. "via host" / "to host" is the host↔firmware exception path — what was not offloaded — so low numbers there mean offload is working. Broadcast and multicast discovery, connection setup, short-lived flows and traffic addressed to the router itself always take that path: a flow is only offloaded once it is established, so a quiet port that carries little else shows a low offloaded share. Port totals are on Status → Overview.')))
	].concat(dsaSection));
}

return view.extend({
	load: getStatus,

	render: function(data) {
		var container = E('div', {}, renderStatus(data));

		poll.add(function() {
			return getStatus().then(function(d) {
				dom.content(container, renderStatus(d));
			});
		}, 10);

		return E('div', {}, [
			E('h2', {}, _('NSS Offload')),
			container
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
