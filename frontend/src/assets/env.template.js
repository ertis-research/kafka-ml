(function(window) {
    window.env = window.env || {};
  
    // Environment variables
    window["env"]["API_SERVER_URL"] = "${BACKEND_URL}";
    window["env"]["ENABLE_FEDML_BLOCKCHAIN"] = "${ENABLE_FEDML_BLOCKCHAIN}";
  })(this);