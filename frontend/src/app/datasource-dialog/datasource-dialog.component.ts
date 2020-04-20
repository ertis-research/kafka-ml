import { Component, Inject } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';

@Component({
  selector: 'app-datasource-dialog',
  templateUrl: './datasource-dialog.component.html',
  styleUrls: ['./datasource-dialog.component.css']
})
export class DatasourceDialogComponent {

  deployment: Number;

  constructor( public dialogRef: MatDialogRef<DatasourceDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any) {}

  onNoClick(): void {
    this.dialogRef.close();
  }
}
