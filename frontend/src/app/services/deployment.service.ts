import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';
import { environment } from '../../environments/environment';
import {Deployment} from '../shared/deployment.model'

@Injectable({
  providedIn: 'root'
})

export class DeploymentService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/deployments/';
    
    getDeployments(){
      return this.httpClient.get<JSON[]>(this.url);
    }

    getDeploymentConfigurationID(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.get(url);
    }

    deleteDeployment(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.delete<JSON>(url);
    }

    deploy(deployment: Deployment){
      return this.httpClient.post(this.url, deployment);
    }



}
