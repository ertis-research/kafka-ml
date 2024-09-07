export const environment = {
  production: true,
  baseUrl: window["env"]["API_SERVER_URL"],
  enableFederatedBlockchain: window["env"]["ENABLE_FEDML_BLOCKCHAIN"] === '1'
};
