import { Component, OnInit } from '@angular/core';
import {DeploymentService} from '../services/deployment.service';
import {ConfigurationService} from '../services/configuration.service';
import {MatSnackBar} from '@angular/material/snack-bar';
import {ActivatedRoute} from '@angular/router';
import {Configuration} from '../shared/configuration.model'

@Component({
  selector: 'app-deployments',
  templateUrl: './deployment-list.component.html',
  styleUrls: ['./deployment-list.component.css']
})
export class DeploymentListComponent implements OnInit {

  constructor(private deploymentService: DeploymentService,
              private configurationService: ConfigurationService,
              private snackbar: MatSnackBar,
              private route: ActivatedRoute) { }
  deployments: JSON[];
  configurationID: number;
  valid: Boolean = true;
  configuration: Configuration;
  filtered_data: string = '';
  ngOnInit(): void {
    if (this.route.snapshot.paramMap.has('id')){
      this.configurationID = Number(this.route.snapshot.paramMap.get('id'));
      this.configurationService.getConfiguration(this.configurationID).subscribe((data)=>{
        this.configuration= <Configuration> data;
        },
        (err)=>{
            this.snackbar.open('Error connecting with the server', '', {
                duration: 3000
            });
            this.valid=false;
        });
      
        if (this.valid){
          this.deploymentService.getDeploymentConfigurationID(this.configurationID).subscribe((data: JSON[])=>{
            this.deployments = data;
            },
            (err)=>{
                this.snackbar.open('Error connecting with the server', '', {
                    duration: 3000
                });
            });
       }
    }else{
      this.deploymentService.getDeployments().subscribe((data: JSON[])=>{
        this.deployments=data;
        },
          (err)=>{
            this.snackbar.open('Error connecting with the server', '', {
                duration: 3000
            });
        });
    }
  }
}
