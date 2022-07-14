import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';

import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})

export class ConfigurationService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/configurations/';
    
    getConfigurations(){
      return this.httpClient.get<JSON[]>(this.url);
    }
    
    createConfiguration(data: JSON){
      return this.httpClient.post<JSON>(this.url, data)
    }

    getConfiguration(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.get(url);
    }

    deleteConfiguration(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.delete<JSON>(url);
    }

    editConfiguration(id: number, data: JSON){
      const url = `${this.url}${id}`
      return this.httpClient.put<JSON>(url, data);
    }

    frameworksConfigUrl = this.baseUrl + '/frameworksInConfiguration/';

    getFrameworksUsedInConfiguration(id: number){
      const url = `${this.frameworksConfigUrl}${id}`
      return this.httpClient.get(url);
    }

    distributedConfiguration = this.baseUrl + '/distributedConfiguration/';
    
    getDistributedConfiguration(id: number){
      const url = `${this.distributedConfiguration}${id}`
      return this.httpClient.get(url);
    }
}