import { Component, OnInit } from '@angular/core';
import { Location } from '@angular/common';
import { Deployment } from '../shared/deployment.model'
import { Configuration } from '../shared/configuration.model'
import { ConfigurationService } from '../services/configuration.service';
import { DeploymentService } from '../services/deployment.service';
import { Router, ActivatedRoute } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';

interface AggStrategies {
  value: string;
  viewValue: string;
}

@Component({
  selector: 'app-deployment-view',
  templateUrl: './deployment-view.component.html',
  styleUrls: ['./deployment-view.component.css']
})
export class DeploymentViewComponent implements OnInit {

  constructor(private location: Location,
    private deploymentService: DeploymentService,
    private configurationService: ConfigurationService,
    private snackbar: MatSnackBar,
    private route: ActivatedRoute,
    private router: Router) { }

  deployment: Deployment = new Deployment();
  configuration: Configuration = new Configuration();
  configurationID: number;
  valid: boolean = false;
  detectedFrameworks: string[] = [];
  showIncremental: Boolean = false;
  showFederated: Boolean = false;
  showDistributed: Boolean = false;
  showUnsupervised: Boolean = false;
  hideTimeout: Boolean = false;

  strategies: AggStrategies[] = [
    {value: 'FedAvg',     viewValue: 'Federated Averaging strategy'},
    // {value: 'FedOpt',     viewValue: 'Federated Optim strategy'},
    // {value: 'FedAdagrad', viewValue: 'Federated Adagrad-based strategy'},
    // {value: 'FedAdam',    viewValue: 'Federated Adam strategy'},
    // {value: 'FedYogi',    viewValue: 'Federated Yogi strategy'},
  ];
  
  ngOnInit(): void {
    this.deployment.conf_mat_settings = false;
    if (this.route.snapshot.paramMap.has('id')) {
      this.configurationID = Number(this.route.snapshot.paramMap.get('id'));
      this.configurationService.getConfiguration(this.configurationID).subscribe(
        (data) => {
          this.configuration = <Configuration>data;
          this.valid = true;
          this.configurationService.getFrameworksUsedInConfiguration(this.configurationID).subscribe(
            (data) => {
              this.detectedFrameworks = <string[]>data
            }
          )
          this.configurationService.getDistributedConfiguration(this.configurationID).subscribe(
            (data) => {
              this.showDistributed = Boolean(data)
            }
          )
        },
        (err) => {
          this.snackbar.open('Configuration not found', '', {
            duration: 3000
          });
        });
    }
  }

  federatedControl(e: any) {
    if (e.checked) {
      this.showFederated = true;
      this.hideTimeout = false;
    } else {
      this.showFederated = false;
    }
  }

  incrementalControl(e: any) {
    if (e.checked) {
      this.showIncremental = true;
    } else {
      this.showIncremental = false;
      this.hideTimeout = false;
    }
  }

  timeoutControl(e: any) {
    if (e.checked) {
      this.hideTimeout = true;
    } else {
      this.hideTimeout = false;
    }
  }

  unsupervisedControl(e: any) {
    if (e.checked) {
      this.showUnsupervised = true;
    } else {
      this.showUnsupervised = false;
    }
  }
  
  clearEmptyOrNullFields(deployment: Deployment): Deployment {
    if (deployment.unsupervised_rounds == null) {
      delete deployment.unsupervised_rounds;
    }
    if (deployment.confidence == null) {
      delete deployment.confidence;
    }

    // Distributed settings
    if (deployment.optimizer == '') {
      delete deployment.optimizer;
    }
    if (deployment.learning_rate && deployment.learning_rate.toString() == '') {
      delete deployment.learning_rate;
    }

    if (deployment.loss == '') {
      delete deployment.loss;
    }

    if (deployment.metrics == '') {
      delete deployment.metrics;
    }

    // Incremental settings
    if (deployment.stream_timeout == null) {
      delete deployment.stream_timeout;
    }

    if (deployment.improvement == null) {
      delete deployment.improvement;
    }

    // Federated settings
    if (deployment.agg_rounds == null) {
      delete deployment.agg_rounds;
    }
    if (deployment.min_data == null) {
      delete deployment.min_data;
    }
    if (deployment.agg_strategy == null) {
      delete deployment.agg_strategy;
    }
    if (deployment.data_restriction == null) {
      delete deployment.data_restriction;
    }

    deployment.tf_kwargs_fit = deployment.tf_kwargs_fit || "";
    deployment.tf_kwargs_val = deployment.tf_kwargs_val || "";
    deployment.pth_kwargs_fit = deployment.pth_kwargs_fit || "";
    deployment.pth_kwargs_val = deployment.pth_kwargs_val || "";

    return deployment;
  }
  
  onSubmit(deployment: Deployment) {  
    deployment = this.clearEmptyOrNullFields(deployment);

    deployment.configuration = this.configurationID;

    this.deploymentService.deploy(deployment).subscribe(
      () => {
        this.router.navigateByUrl('/deployments');
      },
      (err) => {
        this.snackbar.open('Error deploying the configuration:' + (err.error), '', {
          duration: 3000
        });
      });
  }

  back() {
    this.location.back();
  }
}