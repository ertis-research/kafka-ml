import { Component, OnInit } from '@angular/core';
import { ResultService } from '../services/result.service';
import { MatTableDataSource } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute } from '@angular/router';
@Component({
  selector: 'app-result-list',
  templateUrl: './result-list.component.html',
  styleUrls: ['./result-list.component.css']
})
export class ResultListComponent implements OnInit {

  displayedColumns = ['id' ,'model', 'train_metrics', 'val_metrics', 'test_metrics', 'training_time', 'status', 'status_changed', 'chart', 'inference', 'manage', 'download'];

  results: JSON[];
  dataSource = new MatTableDataSource(this.results);
  deploymentID: number;
  valid: Boolean = true;
  deployment: string = '';
  interval = null;
  constructor(private resultService: ResultService,
    public dialog: MatDialog,
    private snackbar: MatSnackBar,
    private route: ActivatedRoute) { }

  refreshData(): void {
    if (this.route.snapshot.paramMap.has('id')) {
      this.deploymentID = Number(this.route.snapshot.paramMap.get('id'));
      this.resultService.getResultsDeploymentID(this.deploymentID).subscribe((data: JSON[]) => {
        this.results = data;
        this.dataSource.data = this.results;
        if (this.results.length > 0) {
          this.deployment = this.results[0]['deployment']['time'];
        }
      },
        (err) => {
          this.snackbar.open('Error connecting with the server', '', {
            duration: 3000
          });
        });
    }
    else {
      this.resultService.getResults().subscribe((data: JSON[]) => {
        this.results = data;
        this.dataSource.data = this.results;
      }, (err) => {
        this.snackbar.open('Error connecting with the server', '', {
          duration: 10000
        });
      });
    }
  }
  ngOnInit(): void {
    this.refreshData();
    /* Uncomment to enable automatic refresh
    this.interval = setInterval(() => {
      this.refreshData();
    }, 5000); */
  }

  ngOnDestroy(){
    /* Uncomment to enable automatic refresh
    clearInterval(this.interval);
    */
  }

  applyFilter(value: string) {
    value = value.trim().toLowerCase();
    this.dataSource.filter = value;
  }

  metricsToHTML(str: string){
    return str.replace("\n", "<br>");
  }

  getLastMetric(metrics: JSON){
    if (metrics == null || metrics == undefined){
      return ""
    }
    let metric_types = Object.keys(metrics)
    let res = ""
    metric_types.forEach(function (value) {
      let val = Math.round((metrics[value][metrics[value].length-1] + Number.EPSILON) * 100000) / 100000
      res += value + ": "+ val + "\n"
    }); 
    res = res.slice(0,-1)
    return res
  }

  confirmDeletion(id: number) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Result ' + id }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.delete(id);
      }
    });
  }

  delete(id: number) {
    this.resultService.deleteResult(id).subscribe(
      (data) => { },  //changed
      (err) => {
        this.snackbar.open('Error deleting the result: ' + err.error, '', {
          duration: 3000
        });
      },
      () => {
        this.snackbar.open('Result deleted', '', {
          duration: 3000
        });
        this.deleteRowDataTable(id);
      }
    );
  }

  getTrainedModel(id: number) {
    this.resultService.getTrainedModel(id).subscribe(
      (data) => {
        const blob = new Blob([data.body], {type: data.headers.get('Content-Type')});
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        link.href = url;
        if (data.headers.get('ML-Framework') == "tf"){
          link.download = 'model-result' + id + '.h5';
        }else if (data.headers.get('ML-Framework') == "pth"){
          link.download = 'model-result' + id + '.pth';
        }        
        
        link.click();
      },
      (err) => {
        console.info(err);
        this.snackbar.open('Error downloading the model', '', {
          duration: 3000
        });

      }
    );
  }

  deleteRowDataTable(id: number) {
    const itemIndex = this.dataSource.data.findIndex(obj => obj['id'] === id);
    console.log(itemIndex);
    this.dataSource.data.splice(itemIndex, 1);
    this.dataSource._updateChangeSubscription(); // <-- Refresh the datasource
  }

  confirmStopping(id: number){
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Training result '+id + ' running from Kubernetes'}
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.stopTraining(id);
      }
    });
  }
  stopTraining(id: number){
    this.resultService.stopTraining(id).subscribe(
      (data) => {},  //changed
      (err)=>{
        this.snackbar.open('Error stopping the training: '+err.error, '', {
          duration: 4000
        });
      },
      ()=>{
            this.snackbar.open('Training stopped', '', {
            duration: 3000
          });
          window.location.reload();
        }
   );
  }
}
