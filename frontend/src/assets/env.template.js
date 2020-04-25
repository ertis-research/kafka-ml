(function(window) {
    window.env = window.env || {};
  
    // Environment variables
    window["env"]["API_SERVER_URL"] = "${BACKEND_URL}";
  })(this);