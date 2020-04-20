import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { DatasourceDialogComponent } from './datasource-dialog.component';

describe('DatasourceDialogComponent', () => {
  let component: DatasourceDialogComponent;
  let fixture: ComponentFixture<DatasourceDialogComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ DatasourceDialogComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(DatasourceDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
