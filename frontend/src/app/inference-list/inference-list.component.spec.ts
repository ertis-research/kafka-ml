import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { InferenceListComponent } from './inference-list.component';

describe('InferenceListComponent', () => {
  let component: InferenceListComponent;
  let fixture: ComponentFixture<InferenceListComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ InferenceListComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(InferenceListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
