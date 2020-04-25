import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';

import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})

export class DatasourceService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/datasources/';
    
    getDatasources(){
      return this.httpClient.get<JSON[]>(this.url);
    }
    
    deployDatasource(data: JSON){
      var url = this.url+'kafka'
      return this.httpClient.post<JSON>(url, data)
    }

}
