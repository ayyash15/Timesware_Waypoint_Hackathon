/* Synthetic data â€” Waypoint Group. Not real company/outlet/person data. */
const WP_DATA = {
  today: "Wed, 30 Sep 2026",
  depot: "Peliyagoda",

  capacity: {
    confirmedOrders: 86,
    availableVehicles: 48,
    reeferUsed: 13, reeferTotal: 16,
    vanUsed: 6, vanTotal: 8,
    atRisk: 12
  },

  orders: [
    { id: "ORD-4471", outlet: "Peliyagoda Supermarket", brand: "Fresh", district: "Colombo", temp: "Chilled", volume: "4.2 mÂ³", weight: "610 kg", window: "05:30â€“08:00", access: "Rear dock", status: "Confirmed" },
    { id: "ORD-4472", outlet: "Gampaha Central", brand: "Fresh", district: "Gampaha", temp: "Ambient", volume: "3.1 mÂ³", weight: "480 kg", window: "05:00â€“07:30", access: "Rear dock", status: "Confirmed" },
    { id: "ORD-4473", outlet: "Kandy City Mall", brand: "Fresh", district: "Kandy", temp: "Chilled", volume: "2.8 mÂ³", weight: "390 kg", window: "06:00â€“07:00 (mall)", access: "Mall bay", status: "At risk" },
    { id: "ORD-4474", outlet: "Nugegoda Fresh Corner", brand: "Fresh", district: "Colombo", temp: "Chilled", volume: "3.6 mÂ³", weight: "520 kg", window: "05:30â€“08:00", access: "Rear dock", status: "Confirmed" },
    { id: "ORD-4475", outlet: "Wattala Lane Store", brand: "Fresh", district: "Gampaha", temp: "Ambient", volume: "1.9 mÂ³", weight: "260 kg", window: "05:00â€“07:30", access: "Van only", status: "At risk" },
    { id: "ORD-4476", outlet: "Kurunegala Fresh Hub", brand: "Style", district: "Kurunegala", temp: "Ambient", volume: "5.4 mÂ³", weight: "310 kg", window: "09:00â€“17:00", access: "Street", status: "Confirmed" },
    { id: "ORD-4477", outlet: "Kandy Style Junction", brand: "Style", district: "Kandy", temp: "Ambient", volume: "6.1 mÂ³", weight: "340 kg", window: "10:00â€“13:00 (mall)", access: "Mall bay", status: "At risk" },
    { id: "ORD-4478", outlet: "Colombo Tech Plaza", brand: "Tech", district: "Colombo", temp: "Ambient", volume: "2.2 mÂ³", weight: "410 kg", window: "09:00â€“17:00", access: "Rear dock", status: "Confirmed" },
    { id: "ORD-4479", outlet: "Negombo Fresh Mart", brand: "Fresh", district: "Gampaha", temp: "Chilled", volume: "3.3 mÂ³", weight: "455 kg", window: "05:00â€“07:30", access: "Rear dock", status: "At risk" },
    { id: "ORD-4480", outlet: "Matale Corner Shop", brand: "Fresh", district: "Matale", temp: "Ambient", volume: "1.4 mÂ³", weight: "180 kg", window: "05:30â€“08:00", access: "Van only", status: "At risk" }
  ],

  deferrals: [
    { outlet: "Kandy City Mall", brand: "Fresh", district: "Kandy", reason: "Refrigerated capacity", deferredYesterday: true, daysSince: 2, nextRun: "Fri, 2 Oct" },
    { outlet: "Wattala Lane Store", brand: "Fresh", district: "Gampaha", reason: "Vehicle access", deferredYesterday: false, daysSince: 1, nextRun: "Fri, 2 Oct" },
    { outlet: "Negombo Fresh Mart", brand: "Fresh", district: "Gampaha", reason: "Refrigerated capacity", deferredYesterday: true, daysSince: 3, nextRun: "Fri, 2 Oct" },
    { outlet: "Kandy Style Junction", brand: "Style", district: "Kandy", reason: "Trip time budget", deferredYesterday: false, daysSince: 6, nextRun: "Sat, 3 Oct" },
    { outlet: "Matale Corner Shop", brand: "Fresh", district: "Matale", reason: "Vehicle unavailable", deferredYesterday: true, daysSince: 4, nextRun: "Fri, 2 Oct" }
  ],

  trips: [
    { vehicle: "VEH014", driver: "Ruwan Perera", trip: "Colombo Fresh Â· Trip 1", stop: "3 of 4 Â· Peliyagoda Supermarket", progress: 50, eta: "06:42", status: "In Transit" },
    { vehicle: "VEH021", driver: "Sunil Bandara", trip: "Gampaha Fresh Â· Trip 1", stop: "5 of 5 Â· Wattala Lane Store", progress: 90, eta: "07:05", status: "At Stop" },
    { vehicle: "VEH003", driver: "Nimal Fernando", trip: "Kandy Fresh Â· Trip 1", stop: "Completed", progress: 100, eta: "â€”", status: "Completed" },
    { vehicle: "VEH033", driver: "Kasun Silva", trip: "Colombo Tech Â· Trip 1", stop: "1 of 2 Â· Colombo Tech Plaza", progress: 20, eta: "10:15", status: "Issue Reported" },
    { vehicle: "VEH009", driver: "Priyantha Jayasuriya", trip: "Kurunegala Style Â· Trip 1", stop: "2 of 4 Â· Kurunegala Fresh Hub", progress: 45, eta: "11:30", status: "In Transit" }
  ],

  dockQueue: [
    { vehicle: "VEH014", departure: "04:10", trip: "Colombo Fresh Â· Trip 1", brand: "Fresh", district: "Colombo", status: "Loaded" },
    { vehicle: "VEH021", departure: "04:20", trip: "Gampaha Fresh Â· Trip 1", brand: "Fresh", district: "Gampaha", status: "Loading" },
    { vehicle: "VEH047", departure: "04:35", trip: "Colombo Fresh Â· Trip 2", brand: "Fresh", district: "Colombo", status: "Queued" },
    { vehicle: "VEH009", departure: "08:00", trip: "Kurunegala Style Â· Trip 1", brand: "Style", district: "Kurunegala", status: "Queued" }
  ],

  loadingStops: [
    { seq: 4, outlet: "Nugegoda Fresh Corner", order: "ORD-4474", items: "24 cases", temp: "Chilled", volume: "3.6 mÂ³", access: "Rear dock" },
    { seq: 3, outlet: "Peliyagoda Supermarket", order: "ORD-4471", items: "22 cases", temp: "Chilled", volume: "4.2 mÂ³", access: "Rear dock" },
    { seq: 2, outlet: "Colombo Fresh Circle", order: "ORD-4482", items: "14 cases", temp: "Ambient", volume: "2.6 mÂ³", access: "Street" },
    { seq: 1, outlet: "Borella Fresh Point", order: "ORD-4483", items: "9 cases", temp: "Ambient", volume: "1.8 mÂ³", access: "Street" }
  ],

  driverStops: [
    { seq: 1, outlet: "Borella Fresh Point", eta: "05:12", window: "05:00â€“07:30", status: "Done" },
    { seq: 2, outlet: "Colombo Fresh Circle", eta: "05:38", window: "05:00â€“07:30", status: "Done" },
    { seq: 3, outlet: "Peliyagoda Supermarket", eta: "06:05", window: "05:30â€“08:00", status: "Current" },
    { seq: 4, outlet: "Nugegoda Fresh Corner", eta: "06:42", window: "05:30â€“08:00", status: "Upcoming" }
  ],

  capacityPlanning: [
    { week: "Week of 5 Oct", brand: "Fresh", depot: "Peliyagoda", forecast: "612 mÂ³", chilled: "228 mÂ³", vehiclesNeeded: 34, reeferNeeded: 12 },
    { week: "Week of 5 Oct", brand: "Style", depot: "Peliyagoda", forecast: "180 mÂ³", chilled: "0 mÂ³", vehiclesNeeded: 8, reeferNeeded: 0 },
    { week: "Week of 12 Oct â€” Festival ramp", brand: "Fresh", depot: "Peliyagoda", forecast: "744 mÂ³", chilled: "301 mÂ³", vehiclesNeeded: 41, reeferNeeded: 16 },
    { week: "Week of 12 Oct â€” Festival ramp", brand: "Tech", depot: "Kandy", forecast: "96 mÂ³", chilled: "0 mÂ³", vehiclesNeeded: 5, reeferNeeded: 0 }
  ]
};
