import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { IoTDevicesListComponent } from './iot-devices-list.component';

describe('ModelListComponent', () => {
  let component: IoTDevicesListComponent;
  let fixture: ComponentFixture<IoTDevicesListComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ IoTDevicesListComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(IoTDevicesListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
