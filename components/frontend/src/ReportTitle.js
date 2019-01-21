import React, { Component } from 'react';
import { Form, Icon } from 'semantic-ui-react';


class ReportTitleContainer extends Component {
    constructor(props) {
        super(props);
        this.state = { title: "Quality-time", edit: false }
    }
    componentDidMount() {
        this.fetch_title();
    }
    componentDidUpdate(prevProps) {
        if (prevProps.report_date !== this.props.report_date) {
          this.fetch_title();
        }
      }
    fetch_title() {
        const report_date = this.props.report_date ? this.props.report_date : new Date();
        let self = this;
        fetch(`http://localhost:8080/report?report_date=${report_date.toISOString()}`)
            .then(function (response) {
                return response.json();
            })
            .then(function (json) {
                self.setState({ title: json.title });
            });
    }
    onClick(event) {
        this.setState((state) => ({ edit: true, previous_title: state.title }));
    }
    onChange(event) {
        this.setState({ title: event.target.value });
    }
    onKeyDown(event) {
        if (event.key === "Escape") {
            this.setState((state) => ({ edit: false, title: state.previous_title }))
        }
    }
    onSubmit(event) {
        event.preventDefault();
        this.setState({ edit: false });
        fetch('http://localhost:8080/report/title', {
            method: 'post',
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title: this.state.title })
        })
    }
    render() {
        return (
            <ReportTitle title={this.state.title} edit={this.state.edit}
                onSubmit={(e) => this.onSubmit(e)} onClick={(e) => this.onClick(e)}
                onChange={(e) => this.onChange(e)} onKeyDown={(e) => this.onKeyDown(e)} />)
    }
}

function ReportTitle(props) {
    if (props.edit) {
        return (<ReportTitleInput title={props.title} onSubmit={props.onSubmit} onChange={props.onChange}
            onKeyDown={props.onKeyDown} />)
    }
    return (
        <ReportTitleDisplay title={props.title} onClick={props.onClick} onMouseEnter={props.onMouseEnter}
            onMouseLeave={props.onMouseLeave} />
    )
}

const ReportTitleInput = props =>
    <Form onSubmit={(e) => props.onSubmit(e)}>
        <Form.Input autoFocus focus defaultValue={props.title}
            onChange={props.onChange} onKeyDown={props.onKeyDown} />
    </Form>


class ReportTitleDisplay extends Component {
    constructor(props) {
        super(props);
        this.state = { editable: false }
    }
    onMouseEnter() {
        this.setState({ editable: true })
    }
    onMouseLeave() {
        this.setState({ editable: false })
    }
    render() {
        return (
            <div onClick={this.props.onClick} onMouseEnter={(e) => this.onMouseEnter(e)}
                onMouseLeave={(e) => this.onMouseLeave(e)}>
                <font size="+3">
                    {this.props.title}
                </font>
                {this.state.editable && <Icon size='large' color='grey' name='edit' style={{marginLeft: "10px"}}/>}
            </div>
        )
    }
}


export { ReportTitleContainer };