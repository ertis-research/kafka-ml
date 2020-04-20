import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';
import { environment } from '../environment';

@Injectable({
  providedIn: 'root'
})

export class ResultService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/results/';
    results_deployment_ulr =  this.baseUrl + '/deployments/results/';
    getResults(){
      return this.httpClient.get<JSON[]>(this.url);
    }

    getResultsDeploymentID(id: number){
      const url = `${this.results_deployment_ulr}${id}`
      return this.httpClient.get<JSON[]>(url);
    }

    deleteResult(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.delete<JSON>(url);
    }

    getTrainedModel(id: number){
      const url = `${this.url}model/${id}`
      return this.httpClient.get(url, {responseType: "blob"});
    }

}
