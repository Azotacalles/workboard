import {useState} from "react";

import WorkspaceList from "./WorkspaceList.jsx";

function WorkspaceHome({ user }) {
    const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(null);
    const workspaces = [
        {'id': 1, 'name': 'Workspace 1'},
        {'id': 2, 'name': 'Workspace 2'},
    ]

    return (
        <div>
            <h1>Workspace Home</h1>
            <p>{ user.username }</p>
            <p>{ selectedWorkspaceId }</p>
            <WorkspaceList workspaces={workspaces}
                           selectedId={selectedWorkspaceId}
                           onSelect={setSelectedWorkspaceId}/>
        </div>
    )
}

export default WorkspaceHome;